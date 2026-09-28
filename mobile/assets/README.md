# assets/

Place ici un `icon.png` (1024×1024, fond plein, logo simple) pour que
`flutter_launcher_icons` génère les icônes Android/iOS.

En attendant, un carré violet un uni convient :

```powershell
# Générer un placeholder avec PowerShell (.NET) :
Add-Type -AssemblyName System.Drawing
$bmp = New-Object System.Drawing.Bitmap(1024, 1024)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.Clear([System.Drawing.Color]::FromArgb(26, 16, 51))  # violet profond
$g.FillEllipse([System.Drawing.Brushes]::MediumPurple, 312, 312, 400, 400)
$g.Dispose()
$bmp.Save("$PWD\icon.png", [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
```

Puis lance : `flutter pub run flutter_launcher_icons`
