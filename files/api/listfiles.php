<?php
if ($_SERVER['REQUEST_METHOD'] == 'GET') {
    $files = array_diff(scandir("/scans", SCANDIR_SORT_DESCENDING), array('..', '.'));
    for ($i = 0; $i < min(10, count($files)); $i++) {
            echo "<a class='listitem' href=/download.php?file=".$files[$i].">".$files[$i]."</a><br>";
    }
}
else {
    http_reponse_code(405);
    die("Error: Method not allowed!");
}
?>