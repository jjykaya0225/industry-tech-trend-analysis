param([string]$InPath,[string]$OutHwpx,[string]$PdfPath)
$ErrorActionPreference='Continue'
$hwp = New-Object -ComObject "HWPFrame.HwpObject"
try { $r=$hwp.RegisterModule("FilePathCheckDLL","FilePathCheckerModule"); Write-Output ("RegisterModule="+$r) } catch { Write-Output ("RegisterModule ERR "+$_.Exception.Message) }
# Auto-answer Hancom's own message boxes so headless Open/Save does not block.
try { $hwp.SetMessageBoxMode(0x2FFF01); Write-Output "MsgBoxMode set" } catch { Write-Output ("MsgBoxMode ERR "+$_.Exception.Message) }
Write-Output "opening..."
try { $null = $hwp.Open($InPath,"HWPX","forceopen:true"); Write-Output "OPENED" } catch { Write-Output ("Open ERR "+$_.Exception.Message) }
try { $null = $hwp.SaveAs($OutHwpx,"HWPX",""); Write-Output ("SAVED hwpx="+(Test-Path $OutHwpx)) } catch { Write-Output ("SaveAs ERR "+$_.Exception.Message) }
try {
  $act = $hwp.CreateAction("FileSaveAsPdf"); $set = $act.CreateSet(); $act.GetDefault($set)
  $set.SetItem("FileName",$PdfPath); $set.SetItem("Format","PDF"); $null=$act.Execute($set)
  Write-Output ("PDF="+(Test-Path $PdfPath))
} catch { Write-Output ("PDF ERR "+$_.Exception.Message) }
try { $hwp.Clear(1) } catch {}
try { $hwp.Quit() } catch {}
Write-Output "CANON_DONE"
