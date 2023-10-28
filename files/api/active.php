<?php
exec("ps aux | grep '/[s]canto'", $output, $retVal);
if(!empty($output)) {
        echo("true");
} else {
        echo("false");
}
?>