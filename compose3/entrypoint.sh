#!/bin/bash
set -e

NODE_NAME=${NODE_NAME}
NODE_IP=${NODE_IP}

echo "Starting node: $NODE_NAME ($NODE_IP)"
echo "Running as user: $(id)"

# 1. 启动 etcd
etcd \
  --name ${NODE_NAME} \
  --data-dir /data/etcd \
  --initial-advertise-peer-urls http://${NODE_IP}:2380 \
  --listen-peer-urls http://0.0.0.0:2380 \
  --advertise-client-urls http://${NODE_IP}:2379 \
  --listen-client-urls http://0.0.0.0:2379 \
  --initial-cluster node1=http://node1:2380,node2=http://node2:2380,node3=http://node3:2380 \
  --initial-cluster-state new \
  --initial-cluster-token pgha-etcd &

# 等 etcd 可用
sleep 5

# 2. 启动 patroni (它会拉起 postgres)
exec /home/postgres/src/pkg/patroni /home/postgres/${NODE_NAME}/patroni.yml

