# TinySoul-KM: register the nightly backend auto-start task (00:10 daily).
# The 00:15 reflection requires the backend alive; the lease makes a second
# start while an instance runs exit harmlessly.
$action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument '"D:\ProgramData\RESUME\TinySoul-Agent-main\TinySoul-Agent-main\scripts\km-backend-night.vbs"'
$trigger = New-ScheduledTaskTrigger -Daily -At 00:10
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 23)
Register-ScheduledTask `
    -TaskName "TinySoulKM-nightly-backend" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "TinySoul-KM nightly backend auto-start (00:10) for the 00:15 daily reflection." `
    -Force | Out-Null
Write-Output "registered:"
Get-ScheduledTask -TaskName "TinySoulKM-nightly-backend" |
    Select-Object TaskName, State | Format-Table -AutoSize
