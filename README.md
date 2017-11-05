# AWS Lambda to alert Vroom new cars via email / sms

Vroom.com doesn't not have a conveninet notifications and alerts features.
This lambda exposes Vroom's API to make simple alerts based on cost/milage

Prepare package for AWS Lambda:
```shell
pip install requests -t
zip -r archive.zip ./aws_main.py ./*/
```