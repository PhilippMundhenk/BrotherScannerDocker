<html>
<head>
<?php include 'config.php'; ?>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother <?php echo($MODEL); ?></title>
<?php
		$button_file = $RENAME_GUI_SCANTOFILE ?? "Scan to file";
		$button_email = $RENAME_GUI_SCANTOEMAIL ?? "Scan to email";
		$button_image = $RENAME_GUI_SCANTOIMAGE ?? "Scan to image";
		$button_ocr = $RENAME_GUI_SCANTOOCR ?? "Scan to OCR";
?>
	<script>
		let active = true;
		let init_done = false;
		function start_scan(target) {
			if (active) {
				return;
			}
			// assume command succeeds
			active = true;
			lock_ui(true, false);
			fetch("/scan.php?target=" + target, { method: "POST" });
		}
		function lock_ui(lock, is_init) {
			console.log("buttons " + (lock ? 'locked' : 'unlocked'));
			if (!is_init) {
				document.querySelector("#status").innerText = (active ? 'Scanning' : 'Ready to scan');
				document.querySelector(".scanner").classList.toggle('hidden', !active);
			}
			document.querySelectorAll(".submit").forEach(e => e.disabled = lock);
		}
		async function fetch_files() {
			//todo: maybe compare and merge changes
			const response = await fetch("/listfiles.php");
			const raw_html = (await response.text()) ?? '';
			//put into files section
			document.querySelector("#files").innerHTML = raw_html;
		}
		async function init() {
			// get active state from backend
			const response = await fetch("/active.php");
			const new_active = ((await response.text()) ?? 'false') === 'true';
			if (new_active != active || !init_done) {
				active = new_active;
				// lock buttons if active
				lock_ui(active, false);
			}
			await fetch_files();
			init_done = true;
			// wait 1s
			setTimeout(init, 1000);
		}
	</script>
</head>
<body onload="lock_ui(true, true); init();">
	<div class="form">
			<div class="title">Brother <?php echo($MODEL); ?></div>
			<div class="subtitle">Status: <span class="status" id="status">Loading...</span></div>
			<div class="scanner-wrapper"><div class="scanner hidden"></div></div>
			<div class="cut cut-long"></div>
				<?php 
				   if (!isset($DISABLE_GUI_SCANTOFILE) || $DISABLE_GUI_SCANTOFILE != true) {
						echo('<button onclick="start_scan(\'file\')" class="submit">'.$button_file.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOEMAIL) || $DISABLE_GUI_SCANTOEMAIL != true) {
						echo('<button onclick="start_scan(\'email\')" class="submit">'.$button_email.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOIMAGE) || $DISABLE_GUI_SCANTOIMAGE != true) {
						echo('<button onclick="start_scan(\'image\')" class="submit">'.$button_image.'</button>');
				   }
				   if (!isset($DISABLE_GUI_SCANTOOCR) || $DISABLE_GUI_SCANTOOCR != true) {
						echo('<button onclick="start_scan(\'ocr\')" class="submit">'.$button_ocr.'</button>');
				   }
			   ?>
			<div class="subtitle">Last scanned:</div>
			<div id="files">
			<?php
					$files = array_diff(scandir("/scans", SCANDIR_SORT_DESCENDING), array('..', '.'));
					for ($i = 0; $i < min(10, count($files)); $i++) {
							echo "<a class='listitem' href=/download.php?file=".$files[$i].">".$files[$i]."</a><br>";
					}
			?>
			</div>
	</div>
</body>
</html>