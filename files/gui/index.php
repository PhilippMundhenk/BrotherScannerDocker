<?php include(__DIR__.'/lib/config.php'); ?>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="main.css">
<title>Brother <?php echo($MODEL); ?></title>
	<script>
		let state = "offline";
		let init_done = false;
		async function start_scan(target, self) {
			if (state !== "online") {
				return;
			}
			// assume command succeeds
			state = "scanning";
			lock_ui(true, false);
			self.classList.toggle('loading', true);
			fetch("/scan.php?target=" + target, { method: "POST" });
		}
		function lock_ui(lock, is_init) {
			console.log("buttons " + (lock ? 'locked' : 'unlocked'));
			if (!is_init) {
				document.querySelector("#status").innerText = (state === "scanning" ? 'Scanning' : (state === "online" ? 'Ready to scan' : "Offline"));
				document.querySelector(".scanner").classList.toggle('hidden', (state !== "scanning"));
			}
			document.querySelectorAll(".submit").forEach(e => e.disabled = lock);
			if(!lock) {
				document.querySelectorAll(".submit").forEach(e => e.classList.remove('loading'));
			}
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
			const response = await fetch("/status.php");
			const new_state = await response.text()
			if (new_state != state || !init_done) {
				state = new_state;
				// lock buttons if offline or scanning
				lock_ui(!(state === "online"), false);
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
					$labels = array(
						'file' => $WEBSERVER_LABEL_SCANTOFILE,
						'email' => $WEBSERVER_LABEL_SCANTOEMAIL,
						'image' => $WEBSERVER_LABEL_SCANTOIMAGE,
						'ocr' => $WEBSERVER_LABEL_SCANTOOCR
					);
					$labels = array_filter($labels, function($v) { return $v !== null && strlen($v) !== 0; });
					foreach ($labels as $func => $label) {
						echo('<button onclick="start_scan(\''. $func .'\', this)" class="submit">'.$label.'</button>');
					}
			   ?>
			<div class="subtitle">Last scanned:</div>
			<div id="files">
			</div>
	</div>
</body>
</html>