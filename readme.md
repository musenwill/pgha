## add vip
```
sudo /usr/sbin/ip addr add 172.18.0.210/16 brd 172.18.255.255 dev eth0 label eth0:1
sudo /usr/sbin/arping -q -A -c 1 -b -I eth0 172.18.0.210
```

## del vip
```
sudo /usr/sbin/ip addr del 172.18.0.210/16 dev eth0 label eth0:1
sudo /usr/sbin/arping -q -A -c 1 -b -I eth0 172.18.0.210
sudo /usr/sbin/arping -c 3 -I eth0 -s 172.18.0.210 -172.18.0.1
```

## 查看高可用状态：
```
docker exec -it pgha-node1 /home/postgres/src/pkg/patronictl -c /home/postgres/node1/patroni.yml list
```

## switchover
```
docker exec -it pgha-node1 /home/postgres/src/pkg/patronictl -c /home/postgres/node1/patroni.yml switchover --leader node2 --candidate node1 --force
```

## failover
```
docker exec -it pgha-node1 /home/postgres/src/pkg/patronictl -c /home/postgres/node1/patroni.yml failover --candidate node1 --force
```


## 查看 vip
```
docker exec -it pgha-node3 ip a
```

## 