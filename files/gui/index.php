<html>
<head>
<?php include 'config.php'; ?>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother <?php echo($MODEL); ?></title>
<?php
	if (isset($RENAME_GUI_SCANTOFILE) && $RENAME_GUI_SCANTOFILE) {
		$button_file = $RENAME_GUI_SCANTOFILE;
	} else {
		$button_file = "Scan to file";
	}
	if (isset($RENAME_GUI_SCANTOEMAIL) && $RENAME_GUI_SCANTOEMAIL) {
		$button_email = $RENAME_GUI_SCANTOEMAIL;
	} else {
		$button_email = "Scan to email";
	}
	if (isset($RENAME_GUI_SCANTOIMAGE) && $RENAME_GUI_SCANTOIMAGE) {
		$button_image = $RENAME_GUI_SCANTOIMAGE;
	} else {
		$button_image = "Scan to image";
	}
	if (isset($RENAME_GUI_SCANTOOCR) && $RENAME_GUI_SCANTOOCR) {
		$button_ocr = $RENAME_GUI_SCANTOOCR;
	} else {
		$button_ocr = "Scan to OCR";
	}
?>

</head>
<body>
	<div class="form">
			<div class="title">Brother <?php echo($MODEL); ?></div>
			<div class="cut cut-long"></div>
			<form target="hiddenFrame" action="/scan.php" method="post">
				<?php 
				   if (!isset($DISABLE_GUI_SCANTOFILE) || $DISABLE_GUI_SCANTOFILE != true) {
						echo('<button type="submit" name="target" value="file" class="submit">'.$button_file.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOEMAIL) || $DISABLE_GUI_SCANTOEMAIL != true) {
						echo('<button type="submit" name="target" value="email" class="submit">'.$button_email.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOIMAGE) || $DISABLE_GUI_SCANTOIMAGE != true) {
						echo('<button type="submit" name="target" value="image" class="submit">'.$button_image.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOOCR) || $DISABLE_GUI_SCANTOOCR != true) {
						echo('<button type="submit" name="target" value="ocr" class="submit">'.$button_ocr.'</button>');
				   }
			   ?>
			</form>
			<iframe hidden style="" name="transFrame" id="transFrame"></iframe>
			<div class="subtitle">Last scanned:</div>
			<?php
					$files = scandir("/scans", SCANDIR_SORT_DESCENDING);
					for ($i = 0; $i < 10; $i++) {
							echo "<a class='listitem' href=/download.php?file=".$files[$i].">".$files[$i]."</a><br>";
					}
			?>
	</div>
</body>
</html>

