<?php
include('config.php');
require_once('helper.php');


/**
 * Safeguards the provided target by validating and escaping it.
 *
 * This function checks if the target is non-empty and one of the allowed values ('file', 'email', 'image', 'ocr').
 * If the target is valid, it escapes the shell command to prevent injection attacks.
 * If the target is invalid or empty, it sends a 400 error page.
 *
 * @param string $target The target to be safeguarded.
 * @return string Escaped shell command if the target is valid.
 */
function safe_guard_target($target) {

        if (empty($target)) {
                trigger_error("Invalid scan target", E_API);
                send_json_error(400, 'Invalid target');
        }

        if (in_array($target, array('file','email','image','ocr'))) {
                return escapeshellcmd($target);
        } else {
                trigger_error("Invalid scan target", E_API);
                send_json_error(400, 'Invalid target');
        }
}


/**
 * Triggers a script to scan a document using a Brother scanner.
 *
 * @param string $target The target script to be executed ('file', 'email', 'image', 'ocr').
 * @param int $UID The user ID to execute the script as.
 * @param string $method The method to execute the script ('return' for background execution, 'wait' for synchronous execution).
 *
 * This function uses `sudo` to run a script located at `/opt/brother/scanner/brscan-skey/script/scanto{target}.sh`
 * as the specified user. Depending on the method, it either runs the script in the background or waits for it to complete.
 */
function trigger_script($target, $UID, $method) {

        if ($method == 'return') {
                popen('sudo -b -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh', 'r');
                json(array('message' => 'Scan triggered','method' => 'post','target' => $target));
        } else if ($method == 'wait') {
                shell_exec('sudo -u \#'.$UID.' /opt/brother/scanner/brscan-skey/script/scanto'.$target.'.sh');
                json(array('message' => 'Scan triggered','method' => 'get','target' => $target));
        }
}


$target = safe_guard_target($scanto);

trigger_script($target, $UID, $method);

?>