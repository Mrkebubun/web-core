#!/usr/bin/env python
#
# Indentation is 4 spaces.
#
# Available routes:
#
#   GET  /download/filehash
#   POST /upload
#   GET  /server-usage
#   GET  /disk-usage

import os

from flask import Flask, render_template, request, g, jsonify, send_file
from werkzeug import secure_filename

import settings
import cloudmanager

app = Flask(__name__)
app.config['TEMP_FOLDER'] = 'tmp'
app.config['MAX_CONTENT_LENGTH'] = settings.STORAGE_SIZE


def get_cloud_manager():
    """Instantiate a cloudmanager instance, if needed."""

    cloud_manager = getattr(g, '_cloud_manager', None)
    if cloud_manager is None:
        cloud_manager = g._cloud_manager = cloudmanager.CloudManager(
                settings.DATABASE,
                settings.STORAGE_PATH,
                settings.STORAGE_SIZE)

    return cloud_manager


def human_size(bytes):
    """Humanize a byte amount, by appending a unit suffix."""

    units = ["Bytes", "KiB", "MiB", "GiB"]

    while bytes > 2048 and len(units) > 1:
        units.pop(0)
        bytes = bytes/1024

    return "{0} {1}".format(bytes, units[0])


@app.teardown_appcontext
def close_connection(exception):
    get_cloud_manager().close()



#Upload post method to save files into directory
@app.route("/upload",methods=['POST'])
def upload():
    """Upload a file using cloud manager.

    This may take a while, as it uploads the given
    file to three different host providers (in parallel).

    """

    # Save the uploaded file into a temporary location.
    file        = request.files['file']
    filename    = secure_filename(file.filename)
    temp_name   = os.path.join(app.config['TEMP_FOLDER'], filename)
    file.save(temp_name)

    try:
        result = get_cloud_manager().upload(temp_name)

        if not result:
            return 'Upload Failed', 500
        else:
            return result, 201
    finally:
        os.remove(temp_name)


@app.route("/download/<filehash>",methods=['GET'])
def download(filehash):
    """Download a file from cloud manager.

    This may take a while, since the file may not
    be currently in local cache. If there is no
    file matching the given hash, returns a string
    with an error message.

    """
    cm = get_cloud_manager()

    full_path = cm.warm_up(filehash)
    if full_path is None:
        return 'File not found', 404

    return send_file(full_path,
            attachment_filename=os.path.basename(full_path),
            as_attachment=True)


@app.route("/server-usage",methods=['GET'])
def server_usage():
    """Return total bytes downloaded.

    Returns the number of bytes that were downloaded
    from this server.

    """
    cm = get_cloud_manager()

    return jsonify(bandwidthusage=human_size(cm.downloaded()))


@app.route("/disk-usage",methods=['GET'])
def disk_usage():
    """Return cloud manager disk usage.

    Returns the number of bytes used up by the local
    cache storage.

    """
    cm = get_cloud_manager()

    return jsonify(diskusage(human_size(cm.used_space())))


if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0')
