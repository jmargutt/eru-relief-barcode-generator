from flask import Flask, render_template
from flask import request, escape, send_file, send_from_directory, current_app
from PIL import Image
import random
import pandas as pd
from datetime import date
import os
from barcode import EAN13
from barcode.writer import ImageWriter
import numpy as np
import PyPDF2
import shutil
from utils import delete_blob, check_if_duplicates, add_margin, get_concat_h, get_concat_v, get_image, save_image, save_pdf, get_pdf
import glob
from google.cloud import storage
from google.api_core import exceptions
import io


app = Flask(__name__)
app.config['bucket'] = "eru-relief-barcode-generator.appspot.com"
app.config['codes_blob'] = "barcodes/codes.csv"
app.config['images_tmp'] = "images/tmp"
app.config['images_final'] = "images"
storage_client = storage.Client.from_service_account_json('creds.json')
barcodes_public_url = ""


@app.route("/")
def index():
    # delete old barcodes
    try:
        delete_blob(storage_client, app.config['bucket'], app.config['codes_blob'])
        bucket = storage_client.get_bucket(app.config['bucket'])
        bucket.delete_blobs(blobs=list(bucket.list_blobs(prefix=app.config['images_tmp'])))
        bucket.delete_blobs(blobs=list(bucket.list_blobs(prefix=app.config['images_final'])))
    except exceptions.NotFound:
        pass
    return render_template('form.html')


@app.route("/generate_barcodes", methods=['GET', 'POST'])
def generate_barcodes():
    if request.method == 'GET':
        return f"The URL /data is accessed directly. Try going to '/form' to submit form"
    if request.method == 'POST':
        form_data = request.form
        bucket = storage_client.get_bucket(app.config['bucket'])

        # try:
        no_tickets = int(form_data['no_tickets'])
        codes = random.sample(range(100000000000, 200000000000), no_tickets)
        while check_if_duplicates(codes):
            codes = random.sample(range(100000000000, 200000000000), no_tickets)

        codes.sort()
        df = pd.DataFrame({'barcode': codes})
        df = df.sort_values(by=['barcode'])

        # save codes to csv
        blob = bucket.blob(app.config['codes_blob'])
        blob.upload_from_string(df.to_csv(), 'text/csv')

        list_im_path = []

        for code in codes:
            image_path = app.config['images_tmp'] + f"/{code}.png"
            list_im_path.append(image_path)
            blob = bucket.blob(image_path)

            rv = io.BytesIO()
            EAN13(str(code), writer=ImageWriter()).write(rv)
            blob.upload_from_string(rv.getvalue(), content_type="image/png")

        for image_path in list_im_path:
            im = get_image(bucket, image_path)
            im_new = add_margin(im, 100, 50, 100, 50, (255, 255, 255))
            save_image(im_new, bucket, image_path)

        im_index = 0
        cnt_page = 0
        logo_file = "logos/merged.png"
        mergeFile = PyPDF2.PdfFileMerger()

        while im_index < len(list_im_path):

            print(f"generating page {cnt_page} starting at image {im_index}")
            imreflogo = get_image(bucket, logo_file)
            imlogo = get_image(bucket, logo_file)
            if im_index == 0:
                imref = get_image(bucket, list_im_path[im_index])
                im_index += 1
            else:
                im_index -= 1
                imref = get_image(bucket, list_im_path[im_index])
                im_index += 1

            for cnt_row in range(5):
                for cnt_col in range(2):
                    if im_index < len(list_im_path):
                        img = get_image(bucket, list_im_path[im_index])
                        save_image(get_concat_h(imref, img),
                                   bucket,
                                   f"{app.config['images_tmp']}/row_{cnt_row}.png")
                        imref = get_image(bucket, f"{app.config['images_tmp']}/row_{cnt_row}.png")

                        save_image(get_concat_h(imreflogo, imlogo),
                                   bucket,
                                   f"{app.config['images_tmp']}/rlogo_{cnt_row}.png")
                        imreflogo = get_image(bucket, f"{app.config['images_tmp']}/rlogo_{cnt_row}.png")

                        im_index += 1
                if im_index < len(list_im_path):
                    imref = get_image(bucket, list_im_path[im_index])
                    im_index += 1
                    imreflogo = get_image(bucket, logo_file)

            # merge all rows with barcodes
            list_row_path = []
            for blob in bucket.list_blobs(prefix=app.config['images_tmp']):
                if "row" in blob.name:
                    list_row_path.append(blob.name)
            imref = get_image(bucket, list_row_path[0])

            for im_path in list_row_path[1:]:
                img = get_image(bucket, im_path)
                save_image(get_concat_v(imref, img),
                           bucket,
                           f"{app.config['images_tmp']}/page_{cnt_page}.png")
                imref = get_image(bucket, f"{app.config['images_tmp']}/page_{cnt_page}.png")

            # merge all rows with logos
            list_logo_path = []
            for blob in bucket.list_blobs(prefix=app.config['images_tmp']):
                if "rlogo" in blob.name:
                    list_logo_path.append(blob.name)
            imreflogo = get_image(bucket, list_logo_path[0])

            for im_path in list_logo_path[1:]:
                imlogo = get_image(bucket, im_path)
                save_image(get_concat_v(imreflogo, imlogo),
                           bucket,
                           f"{app.config['images_tmp']}/page_logo_{cnt_page}.png")
                imreflogo = get_image(bucket, f"{app.config['images_tmp']}/page_logo_{cnt_page}.png")

            image1 = get_image(bucket, f"{app.config['images_tmp']}/page_{cnt_page}.png")
            im1 = image1.convert('RGB')
            save_pdf(im1, bucket, f"{app.config['images_tmp']}/page_{cnt_page}.pdf")

            image1 = get_image(bucket, f"{app.config['images_tmp']}/page_logo_{cnt_page}.png")
            im1 = image1.convert('RGB')
            save_pdf(im1, bucket, f"{app.config['images_tmp']}/page_logo_{cnt_page}.pdf")

            mergeFile.append(get_pdf(bucket, f"{app.config['images_tmp']}/page_{cnt_page}.pdf"))
            mergeFile.append(get_pdf(bucket, f"{app.config['images_tmp']}/page_logo_{cnt_page}.pdf"))

            cnt_page += 1

        blob = bucket.blob(f"{app.config['images_final']}/pages_merged.pdf")
        fp = io.BytesIO()
        mergeFile.write(fp)
        blob.upload_from_string(fp.getvalue(), content_type="application/pdf")

        return """<a href="/download_codes">Télécharger codes-barres (pdf à imprimer)</a>"""


@app.route('/download_codes', methods=['GET', 'POST'])
def download_codes():
    bucket = storage_client.get_bucket(app.config['bucket'])
    blob = bucket.blob(app.config['images_final'] + "/pages_merged.pdf")
    with blob.open("rb") as f:
        contents = f.read()
        return send_file(io.BytesIO(contents), mimetype='application/pdf',
                         as_attachment=True, download_name="tickets.pdf")


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7070, debug=True)