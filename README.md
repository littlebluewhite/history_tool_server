# history_tool_server

docker build -t history_tool_server:latest

docker run --name history_tool_server -e SQL_HOST=192.168.1.11 -e REDIS_HOST=192.168.1.11 -e REDIS_PORT=7001 -e INFLUXDB_HOST=192.168.1.11 -p 9488:9488 -d history_tool_server:latest