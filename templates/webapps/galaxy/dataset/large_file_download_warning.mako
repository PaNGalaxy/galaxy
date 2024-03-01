<%inherit file="/base.mako"/>
<%namespace file="/dataset/display.mako" import="render_deleted_data_message" />

${ render_deleted_data_message( data ) }

<div class="warningmessagelarge">
    This is ${file_size} dataset, do you really want to download it?<br />
    <a href="${h.url_for( controller='dataset', action='display', dataset_id=trans.security.encode_id( data.id ), to_ext=data.ext )}">Download large file</a>
</div>
