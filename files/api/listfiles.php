<?php
include_once(__DIR__."/lib/lib.php");

if ($_SERVER['REQUEST_METHOD'] == 'GET') {

    $files = getFileList($SCANS_DIR, GETFILELIST_SORT_CREATEDATE_DESC);
    for ($i = 0; $i < min(10, count($files)); $i++) {
            $replaced = str_replace($SCANS_DIR."/", "", $files[$i]);
            echo "<a class='listitem' href=/download.php?file=" . $replaced . ">" . $replaced . "</a><br>";
    }
}
else {
    http_response_code(405);
    die("Error: Method not allowed!");
}
?>