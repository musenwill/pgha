# 假死检测

1. 连接 leader，建表写数据
```
docker exec -it pgha-node1 /home/postgres/src/pkg/postgres/bin/psql -h localhost

create table car (time timestamptz, color varchar, speed int);
insert into car values (now(), 'red', 78);
```

2. leader 节点的 $PGHOME 目录冻结
```
docker exec -it -u root pgha-node1 fsfreeze -f /data/postgres
```

docker exec -it -u root pgha-node1 dmsetup suspend /data/postgres