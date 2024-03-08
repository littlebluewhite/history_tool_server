import redis
from redis.cluster import ClusterNode
from redis.cluster import RedisCluster


class RedisDB:
    def __init__(self, redis_config):
        self.host = redis_config["host"]
        self.port = redis_config["port"]
        self.db = redis_config["db"]
        self.is_cluster = redis_config["is_cluster"]

    def redis_client(self):
        if self.is_cluster:
            return self.__new_cluster()
        else:
            return self.__new_redis()

    def __new_cluster(self):
        nodes = [ClusterNode(self.host, self.port)]
        return RedisCluster(startup_nodes=nodes)

    def __new_redis(self):
        return redis.Redis(host=self.host,
                           port=self.port,
                           db=self.db)


if __name__ == "__main__":
    pass
