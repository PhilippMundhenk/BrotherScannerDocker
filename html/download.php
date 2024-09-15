<?php
if ($_SERVER['REQUEST_METHOD'] == 'GET') {
        if(array_key_exists("file", $_GET)) {
                $file = $_GET["file"];
                if(str_contains($file, "..") || str_contains($file, "/")) {
                        header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
                        die("Error: Dont't be evil!");
                }
                $filename="/scans/".$file;
                if(file_exists($filename)) {
                        header("Content-type:application/pdf");
                        header("Content-Disposition:attachment;filename=\"$file\"");
                        readfile($filename);
                } else {
                        header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
                        die("Error: File does not exist!");
                }
        } else {
                header($_SERVER["SERVER_PROTOCOL"] . " 400 OK");
                die("Error: No file provided!");
        }
}
?>