Cloudinary
==========

Cloudinary is a cloud service that offers a solution to a web application's entire image management pipeline.

Easily upload images to the cloud. Automatically perform smart image resizing, cropping and conversion without installing any complex software. Integrate Facebook or Twitter profile image extraction in a snap, in any dimension and style to match your website’s graphics requirements. Images are seamlessly delivered through a fast CDN, and much much more.

Cloudinary offers comprehensive APIs and administration capabilities and is easy to integrate with any web application, existing or new.

Cloudinary provides URL and HTTP based APIs that can be easily integrated with any Web development framework.

FTP API for Cloudinary
======================
This code gives you stable method to sync between legacy systems (such as FTP) and Cloudinary's cloud.
It is a flow triggered by S3 bucket Put, Restore, and Remove events, firing up a server-less function and ending up by an API call to Cloudinary.
A diagram and detailed flow description are in the blog post.

## Getting started guide
![](https://res.cloudinary.com/cloudinary/image/upload/see_more_bullet.png)  **Take a look at our blog post: https://cloudinary.com/blog/ftp_api_for_cloudinary_part_1_real_time_synchronization**.

The project includes AWS Lambda code together with AWS IAM sample policies.

## Try it right away

Sign up for a [free account](https://cloudinary.com/users/register/free) so you can try out image transformations and seamless image delivery through CDN.


## Usage

## Whitelist your S3 Cloudinary bucket to read directly from your private S3 bucket
https://cloudinary.com/documentation/upload_images#private_storage_url

## Mandatory environment variables:
- CLOUDINARY_URL => Cloudinary account details as appear in https://cloudinary.com/console under "reveal account details"
- cld_sync_root => Root of the sync folder on your Cloudinary account
- s3_sync_root => Root of the sync folder on S3 bucket

## Optional environment variables:
- notification_url => A webhook to receive the status of each completed operation. Documentation at https://cloudinary.com/documentation/upload_images#upload_notifications
- upload_only_mode => [true / false] Default: false.  
In this mode, deleted files from the FTP source would not be deleted from Cloudinary. This is to allow having a single source of truth at Cloudinary while saving storage from FTP storage.
  The FTP storage can be kept clean by a periodical script, or by hooking to the notification URL above.
- skip_reload_same_etag => [true / false] Default: false.  
This feature is about skipping the upload of objects when there is the same eTag on both systems. Please avoid using it on the following conditions:
    1. When trying to override master files with modified upload presets
    2. When customer"s bucket uses KMS encryption
    3. When the object was loaded in multi-parts to the customer"s bucket - Maybe would be supported later
    4. When there was a short-cycle of overriding and then overriding with the previous version
   (due to S3 eventual consistency)
#define environment variable skip_reload_same_etag=true to enable

## License
Released under the MIT license.
