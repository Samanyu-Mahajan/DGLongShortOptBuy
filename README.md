## Run code
Add the data and prices folders
```
./run.sh <date>
```
if <date> argument is given then this is the start and end date. If not given then it reads from config
To run for all folders in data 
```
./run_dates.sh
```
reports are stores in quantx/reports and logs in quantx/logs
Finally
```
python3 analysis_dates.py
```

to build a final report from individual date wise reports
