from PIL import Image
from google.cloud import storage
import PyPDF2
import io


def get_pdf(bucket, blob_name):
    blob = bucket.blob(blob_name)
    with blob.open("rb") as f:
        blob_bytes = f.read()
        blob_to_read = io.BytesIO(blob_bytes)
        return PyPDF2.PdfFileReader(blob_to_read)


def get_image(bucket, blob_name):
    blob = bucket.blob(blob_name)
    fp = io.BytesIO(blob.download_as_string())
    return Image.open(fp)


def save_pdf(im, bucket, blob_name):
    fp = io.BytesIO()
    im.save(fp, "pdf")
    blob = bucket.blob(blob_name)
    blob.upload_from_string(fp.getvalue(), content_type="application/pdf")


def save_image(im, bucket, blob_name):
    fp = io.BytesIO()
    im.save(fp, "png")
    blob = bucket.blob(blob_name)
    blob.upload_from_string(fp.getvalue(), content_type="image/png")


def delete_blob(storage_client, bucket_name, blob_name):
    """Deletes a blob from the bucket."""
    # bucket_name = "your-bucket-name"
    # blob_name = "your-object-name"

    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.delete()

    print("Blob {} deleted.".format(blob_name))


def check_if_duplicates(lsit_of_elems):
    """ Check if given list contains any duplicates """
    if len(lsit_of_elems) == len(set(lsit_of_elems)):
        return False
    else:
        return True


def add_margin(pil_img, top, right, bottom, left, color):
    """ Add white margins to image """
    width, height = pil_img.size
    new_width = width + right + left
    new_height = height + top + bottom
    result = Image.new(pil_img.mode, (new_width, new_height), color)
    result.paste(pil_img, (left, top))
    return result


def get_concat_h(im1, im2):
    """ Concatenate images horizontally """
    dst = Image.new('RGB', (im1.width + im2.width, im1.height))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (im1.width, 0))
    return dst


def get_concat_v(im1, im2):
    """ Concatenate images vertically """
    dst = Image.new('RGB', (im1.width, im1.height + im2.height))
    dst.paste(im1, (0, 0))
    dst.paste(im2, (0, im1.height))
    return dst