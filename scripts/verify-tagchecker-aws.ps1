#!/usr/bin/env pwsh
# Smoke-check Tag Checker AWS resources (run from repo root).
# Requires: AWS CLI configured, region us-east-1 (or set $Env:AWS_REGION).

$ErrorActionPreference = "Stop"
$Region = if ($Env:AWS_REGION) { $Env:AWS_REGION } else { "us-east-1" }

$CLUSTER = "tagchecker-ecs-cluster"
$SERVICE = "tagchecker-api-svc"
$ECR_REPO = "tagchecker-api"
$TG_NAME = "tagchecker-api-tg"

function Ok($msg) { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Fail($msg) { Write-Host "[FAIL] $msg" -ForegroundColor Red }

Write-Host "`n=== Tag Checker AWS verify ($Region) ===`n"

try {
    $acct = aws sts get-caller-identity --query Account --output text
    Ok "STS Account: $acct"
} catch {
    Fail "AWS CLI / credentials"; exit 1
}

$r = aws ecs describe-clusters --clusters $CLUSTER --region $Region --query "clusters[0].status" --output text 2>$null
if ($r -eq "ACTIVE") { Ok "ECS cluster '$CLUSTER'" } else { Fail "ECS cluster missing or inactive"; exit 1 }

$svc = aws ecs describe-services --cluster $CLUSTER --services $SERVICE --region $Region --query "services[0]" --output json 2>$null | ConvertFrom-Json
if (-not $svc.serviceName) { Fail "ECS service '$SERVICE' not found"; exit 1 }
Ok "ECS service '$SERVICE' (running=$($svc.runningCount)/desired=$($svc.desiredCount))"

$tdef = aws ecs describe-task-definition --task-definition $($svc.taskDefinition.Split("/")[-1]) --region $Region --query "taskDefinition.containerDefinitions[0]" --output json | ConvertFrom-Json
if ($tdef.name -ne "api") { Fail "Container name expected 'api', got $($tdef.name)"; exit 1 }
$port = $tdef.portMappings[0].containerPort
if ($port -ne 8000) { Fail "Container port expected 8000, got $port"; exit 1 }
Ok "Task container 'api' on port $port"

$imgs = aws ecr list-images --repository-name $ECR_REPO --region $Region --query "length(imageIds)" --output text
if ([int]$imgs -lt 1) { Fail "ECR '$ECR_REPO' has no images"; exit 1 }
Ok "ECR '$ECR_REPO' has images"

$alb = aws elbv2 describe-load-balancers --region $Region --query "LoadBalancers[?LoadBalancerName=='tagchecker-alb'].DNSName|[0]" --output text
if (-not $alb) { Fail "ALB tagchecker-alb not found"; exit 1 }
Ok "ALB DNS: $alb"

$tg = aws elbv2 describe-target-groups --names $TG_NAME --region $Region --query "TargetGroups[0].TargetGroupArn" --output text
$healthy = aws elbv2 describe-target-health --target-group-arn $tg --region $Region --query "TargetHealthDescriptions[?TargetHealth.State=='healthy'] | length(@)" --output text
if ([int]$healthy -lt 1) { Fail "Target group has no healthy targets"; exit 1 }
Ok "Target group '$TG_NAME': $healthy healthy"

try {
    $resp = Invoke-WebRequest -Uri "http://$alb/health" -UseBasicParsing -TimeoutSec 15
    if ($resp.StatusCode -eq 200) { Ok "HTTP /health -> $($resp.Content)" }
    else { Fail "HTTP /health status $($resp.StatusCode)"; exit 1 }
} catch {
    Fail "HTTP /health failed: $($_.Exception.Message)"
    exit 1
}

Write-Host "`nAll checks passed.`n"
