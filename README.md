## Run code
Add the data and prices folders
```
./run.sh
```
OPTIONS = 0 for equity
for nifty
OPTIONS = 1
specify start and end dates in config
build one end of strategy report for all days but logs saved in start date.

to run for all dates in data folder you need to modify main.py and run.sh appropriately and then call
```
./run_dates.sh
```
reports are stores in quantx/reports and logs in quantx/logs
Finally
```
python3 analysis_dates.py
```

to build a final report from individual date wise reports
