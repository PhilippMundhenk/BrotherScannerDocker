<?php 
include('config.php');
require_once('helper.php');

$file_op = False;

if (isset($ALLOW_GUI_FILEOPERATIONS) && $ALLOW_GUI_FILEOPERATIONS) {
  $file_op = True;
}

function list_pdf_files($directory){

  // Get list of files and directories
  $files = scandir($directory);
  
  // Remove '.' and '..' from the list
  $files = array_diff($files, array('.', '..'));
  
  // Create an associative array with filenames and their modification times
  $filesWithMtime = array();
  foreach ($files as $file) {
      $filePath = $directory . '/' . $file;
      if (is_file($filePath) && pathinfo($filePath, PATHINFO_EXTENSION) === 'pdf') { // Filter PDF files
          $filesWithMtime[$file] = array(
              'mtime' => filemtime($filePath),
              'size' => filesize($filePath),
              'permissions' => substr(sprintf('%o', fileperms($filePath)), -4),
              'owner' => posix_getpwuid(fileowner($filePath))['name'],
              'group' => posix_getgrgid(filegroup($filePath))['name'],
          );
      }
  }
  
  // Sort files by modification time (newest first)
  uasort($filesWithMtime, function($a, $b) {
      return $b['mtime'] <=> $a['mtime'];
  });

  return $filesWithMtime;

}

?>
<div class="d-flex flex-column align-items-stretch flex-shrink-0 bg-white" >

  <div class="list-group list-group-flush border-bottom scrollarea">

    <?php 
    foreach (list_pdf_files('/scans') as $file => $attributes) { 

      $file_op_bottons=   '<div class="btn-group btn-group-sm" role="group" aria-label="Basic outlined">
                            <a type="button" class="btn btn-outline-dark" href="/api/file/'.$file.'/download" target="_blank"><i class="far fa-save fa-fw"></i></a>
                          </div>';
      if ($file_op) {
        $file_op_bottons='<div class="btn-group btn-group-sm" role="group" aria-label="Basic outlined">
                            <a type="button" class="btn btn-outline-dark" href="/api/file/'.$file.'/download" target="_blank"><i class="far fa-save fa-fw"></i></a>
                            <button type="button" class="btn btn-outline-dark"><i class="far fa-keyboard fa-fw"></i></button>
                            <button type="button" class="btn btn-outline-dark"><i class="far fa-trash-alt fa-fw"></i></button>
                          </div>';
      }
    ?>

    <div class="list-group-item list-group-item-action py-3" aria-current="true">
      <div class="d-flex w-100 align-items-center justify-content-between">
        <strong class="mb-1"><?php echo $file; ?></strong>
        <small><?php echo date('D', $attributes['mtime']); ?></small>
      </div>
      <div class="d-flex w-100 align-items-center justify-content-between pt-3">
        <div class="mb-1 small"><?php echo number_format($attributes['size']/1024); ?> KB</div>
        <?php echo $file_op_bottons; ?>
      </div>
      
    </div>
    <?php } ?>

  </div>
</div>


