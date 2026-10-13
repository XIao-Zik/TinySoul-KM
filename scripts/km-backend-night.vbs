' TinySoul-KM: nightly backend auto-start (00:10) so the 00:15 daily
' reflection fires with the backend alive. Launches hidden; if an instance
' is already running the second start exits harmlessly ("already running").
CreateObject("Wscript.Shell").Run _
  """D:\anaconda3\envs\TinySoul-PKM\Scripts\tinysoul.exe"" start --root ""D:\ProgramData\RESUME\my-pkm""", _
  0, False
