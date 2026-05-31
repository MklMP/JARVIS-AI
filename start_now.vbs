Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\MKL\Jarvis"
WshShell.Run "cmd.exe /c title Jarvis Server && python server.py", 1, False
