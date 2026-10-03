Set WshShell = CreateObject("WScript.Shell")
scriptDir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
pyScript = scriptDir & "\start_background_service.py"
WshShell.Run "python " & Chr(34) & pyScript & Chr(34), 0, False
Set WshShell = Nothing
