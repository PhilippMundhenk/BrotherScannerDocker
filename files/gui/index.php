<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother Scanner</title>
<?php
	if (array_key_exists('RENAME_GUI_SCANTOFILE', $_ENV)) {
		$button_file = $_ENV["RENAME_GUI_SCANTOFILE"];
	} else {
		$button_file = "Scan to file";
	}
	if (array_key_exists('RENAME_GUI_SCANTOEMAIL', $_ENV)) {
		$button_email = $_ENV["RENAME_GUI_SCANTOEMAIL"];
	} else {
		$button_email = "Scan to email";
	}
	if (array_key_exists('RENAME_GUI_SCANTOIMAGE', $_ENV)) {
		$button_image = $_ENV["RENAME_GUI_SCANTOIMAGE"];
	} else {
		$button_image = "Scan to image";
	}
	if (array_key_exists('RENAME_GUI_SCANTOIMAGE', $_ENV)) {
		$button_ocr = $_ENV["RENAME_GUI_SCANTOOCR"];
	} else {
		$button_ocr = "Scan to OCR";
	}
?>

</head>
<body>
	<div class="form">
			<div class="title">Brother Scanner</div>
			<div class="cut cut-long"></div>
			<form action="/scan.php" method="get">
				<button type="submit" name="target" value="file" class="submit"><?php $button_file ?></button>
				<button type="submit" name="target" value="email" class="submit"><?php $button_email ?></button>
				<button type="submit" name="target" value="image" class="submit"><?php $button_image ?></button>
				<button type="submit" name="target" value="ocr" class="submit"><?php $button_ocr ?></button>
			</form>
	</div>
</body>
</html>

