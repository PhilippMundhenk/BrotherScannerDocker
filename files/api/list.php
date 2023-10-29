<?php
if ($_SERVER['REQUEST_METHOD'] == 'GET') {
        $files = scandir("/scans", SCANDIR_SORT_DESCENDING);
        if(array_key_exists("num", $_GET)) {
                $num = $_GET["num"];
        } else {
                $num = count($files);
        }
        for ($i = 0; $i < $num; $i++) {
                echo $files[$i]."<br>";
        }
}
?>