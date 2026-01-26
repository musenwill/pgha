FROM pg_compiler:centos_260121

COPY src/patroni /home/postgres/patroni
RUN cd /home/postgres/patroni && pip3 install ".[etcd]" --no-build-isolation
RUN rm -rf /home/postgres/patroni

CMD ["fish"]
