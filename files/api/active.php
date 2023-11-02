<?php
exec("ps aux | grep '[s]canimage'", $output, $retVal);
if(!empty($output)) {
        echo("true");
} else {
        echo("false");
}
?>