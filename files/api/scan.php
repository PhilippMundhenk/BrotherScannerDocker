<?php
ini_set('display_errors', 1);
ini_set('display_startup_errors', 1);
error_reporting(E_ALL);

include_once(__DIR__."/lib/config.php");
include_once(__DIR__."/lib/lib.php");

function exit_error() {
        http_response_code(400);
        die("Error: Thou shalt not inject unknown script names!");
}


$target = $_POST["target"] ?? ($_GET["target"] ?? '');

if (empty($target)) {
        http_response_code(400);
        die("Error: No scanning function selected (try append: ?target=<file|email|image|ocr>)");
}
if (in_array($target, array('file','email','image','ocr'))) {

        $script = $SCRIPTS_DIR . "/scanto" . $target . ".sh";

        if(!is_sub_path($script, $SCRIPTS_DIR)) {
                exit_error();
        }
        if ($_SERVER['REQUEST_METHOD'] == 'POST') {
                //return immediately
                $handle = popen($script, 'r');
        } else if ($_SERVER['REQUEST_METHOD'] == 'GET') {
                //wait for completion
                $output=shell_exec($script);
        }
}
else
{
        exit_error();
}

//TODO: Fix serving of file on get
//if ($_SERVER['REQUEST_METHOD'] == 'GET') {
//      $files = scandir('/scans', SCANDIR_SORT_DESCENDING);
//      $newest_file = $files[0];
//      header($_SERVER["SERVER_PROTOCOL"] . " 200 OK");
//      header("Cache-Control: public"); // needed for internet explorer
//      header("Content-Type: application/pdf");
//      header("Content-Transfer-Encoding: Binary");
//      header("Content-Length:".filesize($newest_file));
//      readfile($newest_file);
//      die();
//}

?>