#!/bin/bash
readonly cb_name=$1
readonly role=$2
readonly scope=$3

# 以下参数请根据实际情况填写，可参考步骤 5 返回的网卡信息
VIP=172.18.0.200            # 虚拟 IP
VIPBRD=172.18.255.255       # 广播地址
VIPNETMASK=255.255.0.0      # 子网掩码
VIPNETMASKBIT=16            # 网络前缀

# VIP ifconfig
VIPDEV=eth0                 # 绑定VIP的网络接口
VIPLABEL=1                  # 网口接口标签
GATEIP=172.18.0.1           # ip r ，这将显示详细的路由信息，其中默认网关将以“default via”的形式展示        

function usage() {
    echo "Usage: $0 <on_start|on_stop|on_role_change> <role> <scope>"; >> /data/vip.log
    exit 1;
}

function addvip(){
    echo "`date +%Y-%m-%d\ %H:%M:%S,%3N` INFO: /usr/sbin/ip addr add ${VIP}/${VIPNETMASKBIT} brd ${VIPBRD} dev ${VIPDEV} label ${VIPDEV}:${VIPLABEL}" >> /data/vip.log
    sudo /usr/sbin/ip addr add ${VIP}/${VIPNETMASKBIT} brd ${VIPBRD} dev ${VIPDEV} label ${VIPDEV}:${VIPLABEL}
    sudo /usr/sbin/arping -q -A -c 1 -b -I ${VIPDEV} ${VIP}
}

function delvip(){
    echo "`date +%Y-%m-%d\ %H:%M:%S,%3N` INFO: sudo /usr/sbin/ip addr del ${VIP}/${VIPNETMASKBIT} dev ${VIPDEV} label ${VIPDEV}:${VIPLABEL}" >> /data/vip.log
    sudo /usr/sbin/ip addr del ${VIP}/${VIPNETMASKBIT} dev ${VIPDEV} label ${VIPDEV}:${VIPLABEL}
    sudo /usr/sbin/arping -q -A -c 1 -b -I ${VIPDEV} ${VIP}
    sudo /usr/sbin/arping -c 3 -I ${VIPDEV} -s ${VIP} -${GATEIP}
}

echo "`date +%Y-%m-%d\ %H:%M:%S,%3N` WARNING: has callback $cb_name $role $scope" >> /data/vip.log

# on patroni 4.10, use primary instead of master
case $cb_name in
    on_stop)
        delvip
        ;;
    on_start)
        if [[ $role == 'primary' ]]||[[ $role == 'master' ]]||[[ $role == 'leader' ]]; then
            addvip
        fi
        ;;
    on_role_change)
        if [[ $role == 'primary' ]]||[[ $role == 'master' ]]; then
            addvip
        elif [[ $role == 'slave' ]]||[[ $role == 'replica' ]]||[[ $role == 'logical' ]]||[[ $role == 'standby' ]]; then
            delvip
        fi
        ;; 
    *)
        usage
        ;;
esac
