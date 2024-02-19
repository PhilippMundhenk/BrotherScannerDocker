<?php
if ($_SERVER['REQUEST_METHOD'] == 'GET') {
        if(array_key_exists("file", $_GET)) {
                $file = $_GET["file"];
                if(str_contains($file, "..") || str_contains($file, "/")) {
                        http_reponse_code(400);
                        die("Error: Dont't be evil!");
                }
                $filename="/scans/".$file;
                if(file_exists($filename)) {
                        header("Content-type: application/pdf");
                        header("Content-Disposition: attachment;filename=\"scan.pdf\"");
                        readfile($filename);
                } else {
                        http_reponse_code(404);
                        die("Error: File does not exist!");
                }
        } else {
                http_reponse_code(400);
                die("Error: No file provided!");
        }
} else {
        http_reponse_code(405);
        die("Error: Method not allowed!");
}
?>