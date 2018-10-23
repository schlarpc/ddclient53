# ddclient53

ddclient-compatible route53 updater, works with dyndns2 protocol. Pretty hacky but works.

## deploying

`aws cloudformation deploy --template-file <(python3 template.py) --stack-name ddclient53 --capabilities CAPABILITY_IAM --parameter-overrides ...`

## why?

I wanted to use the built-in dynamic DNS functionality of my router.
