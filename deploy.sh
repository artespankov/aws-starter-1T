#!/bin/bash
set -e
command -v aws >/dev/null 2>&1 || { echo "First, install the AWS CLI: python -m pip install --upgrade awscli." >&2; exit 1; }

app=icalculator

user=$(aws iam get-user --output text --query 'User.UserName')
aws_region=us-east-1
template=template.yaml
swagger=swagger.yaml
use_previous_value=true
stage=${1:-dev-$user}
version=$(date -u "+%Y-%m-%dT%H%M%SZ")

if [[ "$stage" == *prod* ]]; then
    stack=${app}
    env_type=prod
    code_bucket=dti1ticket-releases
    aws_profile=dti1ticketprod
else
    stack=${app}-${user}
    env_type=dev
    code_bucket=etix-releases-dev
    aws_profile=1ticketdev
fi
release=${stack}-${version}
release_swagger=swagger-${release}.yaml
aws_account_id=$(aws sts get-caller-identity --output text --query 'Account' --profile=$aws_profile)

# Fill in variables in swagger file, copy to S3, then remove
echo "Creating ${release_swagger}..."
sed -e "s/<<region>>/$aws_region/g" \
    -e "s/<<accountId>>/$aws_account_id/g" \
    -e "s/<<service>>/$app/g" \
    -e "s/<<stage>>/$stage/g" \
    -e "s/<<stack>>/$stack/g" \
    < $swagger > $release_swagger
aws s3 cp ${release_swagger} s3://${code_bucket}/ --profile=$aws_profile
rm $release_swagger

# Unzip vendored packages into release package
echo "Packaging ${release}..."
rm -rf $release
mkdir $release
if [ -d vendored ]; then
    for package in vendored/*.zip
    do
        unzip -d $release -q -o -u $package
    done
fi

# Copy code into release package
cp -R $app $release

# Zip up release package
cd $release
zip -rq9 ${release}.zip *

# Copy release package to S3
aws s3 cp ${release}.zip s3://${code_bucket}/ --profile=$aws_profile

# Remove release package
cd ..
rm -rf $release

# Deploy the CloudFormation template
echo "Deploying $version to ${stack}..."
aws cloudformation deploy \
    --region $aws_region \
    --profile $aws_profile \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides ServiceName=$app \
                          StageName=$stage \
                          CodeBucketName=$code_bucket \
                          CodeKey=${release}.zip \
                          EnvironmentType=${env_type} \
                          SwaggerKey=${release_swagger} \
    --stack-name $stack \
    --template-file $template \
    --tags app-name=$stack

echo "Describing..."
aws cloudformation describe-stacks \
    --region $aws_region \
    --profile $aws_profile \
    --stack-name ${stack} \
| python -m json.tool

echo ""
echo "Have a great day."
echo ""
