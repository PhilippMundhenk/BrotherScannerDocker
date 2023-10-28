<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother Scanner</title>
<?php
	$button_file = $_ENV["RENAME_GUI_SCANTOFILE"];
	if(empty($_ENV["RENAME_GUI_SCANTOFILE"]))
	{
		$button_file = "Scan to file";
	}
	$button_email = $_ENV["RENAME_GUI_SCANTOEMAIL"];
	if(empty($_ENV["RENAME_GUI_SCANTOEMAIL"]))
	{
		$button_email = "Scan to email";
	}
	$button_image = $_ENV["RENAME_GUI_SCANTOIMAGE"];
	if(empty($_ENV["RENAME_GUI_SCANTOIMAGE"]))
	{
		$button_image = "Scan to image";
	}
	$button_ocr = $_ENV["RENAME_GUI_SCANTOOCR"];
	if(empty($_ENV["RENAME_GUI_SCANTOOCR"]))
	{
		$button_ocr = "Scan to OCR";
	}
?>

</head>
<body>
	<div class="form">
			<div class="title">Brother Scanner</div>
			<div class="cut cut-long"></div>
			<form action="/scan.php?target=file" method="get">
				<button type="submit" name="action" class="submit"><?php $button_file ?></button>
			</form>
			<form action="/scan.php?target=email" method="get">
				<button type="submit" name="action" class="submit"><?php $button_email ?></button>
			</form>
			<form action="/scan.php?target=image" method="get">
				<button type="submit" name="action" class="submit"><?php $button_image ?></button>
			</form>
			<form action="/scan.php?target=ocr" method="get">
				<button type="submit" name="action" class="submit"><?php $button_ocr ?></button>
			</form>
	</div>
</body>
</html>

