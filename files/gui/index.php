<html>
<head>
<?php include 'config.php'; ?>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother <?php echo($MODEL); ?></title>
<?php
	if ($RENAME_GUI_SCANTOFILE) {
		$button_file = $RENAME_GUI_SCANTOFILE;
	} else {
		$button_file = "Scan to file";
	}
	if ($RENAME_GUI_SCANTOEMAIL) {
		$button_email = $RENAME_GUI_SCANTOEMAIL;
	} else {
		$button_email = "Scan to email";
	}
	if ($RENAME_GUI_SCANTOIMAGE) {
		$button_image = $RENAME_GUI_SCANTOIMAGE;
	} else {
		$button_image = "Scan to image";
	}
	if ($RENAME_GUI_SCANTOIMAGE) {
		$button_ocr = $RENAME_GUI_SCANTOOCR;
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
				<?php 
				   if ($DISABLE_GUI_SCANTOFILE != true) {
						echo('<button type="submit" name="target" value="file" class="submit">'.$button_file.'</button>');
				   }
				   if ($DISABLE_GUI_SCANTOEMAIL != true) {
						echo('<button type="submit" name="target" value="email" class="submit">'.$button_email.'</button>');
				   }
				   if ($DISABLE_GUI_SCANTOIMAGE != true) {
						echo('<button type="submit" name="target" value="image" class="submit">'.$button_image.'</button>');
				   }
				   if ($DISABLE_GUI_SCANTOOCR != true) {
						echo('<button type="submit" name="target" value="ocr" class="submit">'.$button_ocr.'</button>');
				   }
			   ?>
			</form>
	</div>
</body>
</html>

