<?php
if ($_SERVER['REQUEST_METHOD'] == 'GET') {
        $files = array_diff(scandir("/scans", SCANDIR_SORT_DESCENDING), array('..', '.'));
        $num = $_GET["num"] ?? count($files);
        for ($i = 0; $i < $num; $i++) {
                echo $files[$i]."<br>";
        }
}
?>
