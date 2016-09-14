## Multicast test tool
### How to use ##

Edit the script and modify the following variables to fit your environment:

    DB_HOST = '127.0.0.1'
    DB_PORT = 8086
    DB_NAME = 'mcast'
    DB_USER = 'root'
    DB_PASS = 'root'
    INTER_PKT_INTERVAL = 0.1
    TTL = 8
    REPORT_INTERVAL = 5 # How often in seconds we write to the database

Start the test tool as server

    ./mcast.py -s 239.100.100.1 -p 30001

Or start the test tool as client

    ./mcast.py -c 239.100.100.1 -p 30001

The data server will log data into the 'traffic' measurement every $REPORT_INTERVAL

    name: traffic
    -------------
    time                    group           total_good      total_invalid   total_lost      total_received
    1473819980381305251     239.255.1.2     50              0               0               50
    1473819985399869019     239.255.1.2     50              0               0               50
    1473819985948824919     239.255.1.2     51              0               0               51
    1473819990418000164     239.255.1.2     50              0               0               50


