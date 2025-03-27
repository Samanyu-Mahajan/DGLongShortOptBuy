## Run code
```
./run.sh
```
The logs will be updated in quantx/logs/{date}/{time_gap}
default time gap in seconds after which update(on_timer) function is called is 5s (TIMER_TIME_SECONDS = 5). can be changed in CONFIG. 
To pass it as a command line argument, update ./run.sh (add the $1)
```
python3 quantx/main.py "$1"
```
and then run using
```
./run.sh 10
```
To run for time gaps in [5,10,15... 60] run ./run_loop.sh with the updated ./run.sh (with the added "$1"):
```
./run_loop.sh
```
In cofig if you want to run for a particular universe then set UNIVERSE and set NUM_TOKENS = 0.
If NUM_TOKENS is non zero it will obtain the universe as the top NUM_TOKENS tokens with highest number of packets and ignore the UNIVERSE specified in config
