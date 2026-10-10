<?php 
include('config.php');
require_once('helper.php');

$file_op = False;

if (isset($ALLOW_GUI_FILEOPERATIONS) && $ALLOW_GUI_FILEOPERATIONS) {
  $file_op = True;
}



?>
<div class="d-flex flex-column align-items-stretch flex-shrink-0 bg-white" id="fileslist" >

  <div class="list-group list-group-flush border-bottom scrollarea">

    <?php 
    $i=1;
    foreach (list_files('/scans/') as $file) { 
    ?>
    <div class="list-group-item list-group-item-action py-3" aria-current="true" id="file_<?php echo $i; ?>">
      <div class="d-flex w-100 align-items-center justify-content-between">
        <strong class="mb-2 file-name"><?php echo $file['name']; ?></strong>
        <input class="form-control form-control-sm file-name-new d-none m-0 me-2 " type="text" value="<?php echo $file['name_clean']; ?>">
        <input class="form-control form-control-sm file-name-original d-none m-0 me-2 " type="hidden" value="<?php echo $file['name_clean']; ?>">
        <small><?php echo date('D', $file['fileModificationTime']); ?></small>
      </div>
      <div class="d-flex w-100 align-items-center justify-content-between pt-3">
        <div class="mb-1 small info-label file-info-label-default"><?php echo number_format($file['size']/1024); ?> KB</div>
        <div class="mb-1 small info-label file-info-label-delete d-none">Are you sure you want to delete this file?</div>
        <div class="mb-1 small info-label file-info-label-rename d-none">

              <div class="form-check  form-switch">
                <input class="form-check-input file-rename-prefix-none" type="radio" name="file-rename-prefix<?php echo $i; ?>" id="prefixnone<?php echo $i; ?>">
                <label class="form-check-label" for="prefixnone<?php echo $i; ?>">No prefix</label>
              </div>

              <div class="form-check  form-switch">
                <input class="form-check-input file-rename-prefix-date" type="radio" name="file-rename-prefix<?php echo $i; ?>" id="prefixdate<?php echo $i; ?>" checked>
                <label class="form-check-label" for="prefixdate<?php echo $i; ?>">Date prefix</label>
              </div>

              <div class="form-check form-switch">
                <input class="form-check-input file-rename-prefix-datetime" type="radio" name="file-rename-prefix<?php echo $i; ?>" id="prefixdatetime<?php echo $i; ?>">
                <label class="form-check-label" for="prefixdatetime<?php echo $i; ?>">Date & time prefix</label>
              </div>
            
          
        </div>
        <div class="list-group list-group-flush border-bottom scrollarea file-buttons-default">
          <div class="btn-group" role="group" aria-label="Basic outlined">
            <a type="button" class="btn btn-outline-dark" href="/api/file/<?php echo $file['file']; ?>/download" target="_blank">
              <i class="far fa-save fa-fw"></i>
            </a>
            <?php if ($file_op) { ?>
            <button type="button" class="btn btn-outline-dark file-rename">
              <i class="far fa-keyboard fa-fw"></i>
            </button>
            <button type="button" class="btn btn-outline-dark file-delete">
              <i class="far fa-trash-alt fa-fw"></i>
            </button>
            <?php } ?>
          </div>
        </div>
        <div class="list-group list-group-flush border-bottom scrollarea file-buttons-delete d-none">
          <div class="btn-group" role="group" aria-label="Basic outlined">
            <button type="button" class="btn btn-outline-dark file-delete-cancel"> CANCEL </button>
            <a type="button" class="btn btn-danger file-delete-confirm" href="/api/file/<?php echo $file['file']; ?>/delete"> DELETE </a>
          </div>
        </div>
        <div class="list-group list-group-flush border-bottom scrollarea file-buttons-rename d-none">
          <div class="btn-group" role="group" aria-label="Basic outlined">
            <button type="button" class="btn btn-outline-dark file-rename-cancel"> CANCEL </button>
            <a type="button" class="btn btn-danger file-rename-confirm" href="/api/file/<?php echo $file['file']; ?>/rename"> SAVE </a>
          </div>
        </div>
      </div>
    </div>
    <?php 
    $i++;
    }
    ?>


  </div>
</div>


