import os, sys, os.path, json, random, urllib, subprocess # imgboard by joshek
import hashlib, datetime, cgi, base64, string, io # tested on python 3.8.5
from http.server import HTTPServer, BaseHTTPRequestHandler 
from socketserver import ThreadingMixIn
from tinydb import TinyDB, Query
from datetime import datetime

with open('./config.json', 'r') as config_file:
    configs = json.load(config_file)
address=(configs["address"]) # IP address to bind imgboard to
port=(configs["port"]) # port to run imgboard on
board_name=(configs["board_name"]) # site name of the imageboard
image_dir=(configs["image_dir"]) # directory where images are stored after upload
max_upload=(configs["max_upload_size"]) # upload size limit
charmap=(configs["charmap"]) # character encoding to use
log = TinyDB((configs["upload_db"]), indent=4) # upload logging database
search = Query()

def generateFilename(length): # generate random file for uploads
    letters = string.ascii_letters
    result_str = ''.join(random.choice(letters) for i in range(length))
    return str(result_str) # return the filename

def getFileMime(filename): # get uploaded file mimetype for file extension
    if [".png" in filename] == True:
        return "image/png"
    if [".jpg" in filename] == True:
        return "image/jpeg"
    if [".gif" in filename] == True:
        return "image/gif"
    if [".webm" in filename] == True:
        return "video/webm"

def loadCSS(): # rather than embed all the CSS in this python file, lets put it in a seperate file and just read it when needed
        with open("www/style.css") as css:
            return css.read()

def getPosts(): # search the image_dir folder and store the HTML output to a text file to reduce the load on the server
    for directory, subdirectories, files in os.walk(image_dir, topdown=True):
        for file in files:
            if file == ".DS_Store": # exclude certain files from being indexed
                continue
            else:
                with open(os.path.join(directory, file), "rb") as img_file:
                    mimetype=(getFileMime(file))
                    post_details=(log.search(search.filename == file))
                    image_data=(base64.b64encode(img_file.read()).decode(charmap))
                    image_element=("""<img src="data:{};base64, {}">""".format(mimetype, image_data))
                    image_container=("""<div class="image"><p class="tripcode">{}</p>{}</div>""".format((str(post_details)[2:-2]), image_element))
                    with open("./.imagecache", "a+") as image_log:
                        image_log.write(image_container)
                        image_log.close()
        
def countPosts(): # get upload count, only counts files
    list = next(os.walk(image_dir))[2]
    if len(list) == "1":
        return "{} picture".format(len(list))
    else:
        return "{} pictures".format(len(list))

def readImageCache(): # read the image cache and save it to ./.imagecache
    getPosts()
    f = open("./.imagecache", "r")
    contents = f.read()
    return contents

def purgeImageCache(): # purge the saved image cache
    f = open("./.imagecache", 'r+')
    f.truncate(0)

def restart(): # restart imgboard to refresh posts
    print("Restarting...")
    os.execv(sys.executable, ['sudo python3'] + sys.argv)

def tripcode(ip, name): # generate uploader tripcode
    triphash = "{}!{}".format(str(ip), str(name)).encode(charmap)
    triphash = hashlib.sha1(triphash)
    trip_hashed = triphash.hexdigest()
    tripcode=("{}!{}".format(name, trip_hashed))
    return tripcode

class homepage:
    br=(str("<br>").encode(charmap))
    meta=("""<title>{} - home</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="30"/>
    <style>{}</style>""".format(board_name, loadCSS()))
    heading=("""<div class="heading">
    <h2 class="title">{}</h2>
    <p class="counter">{}</p></div>""".format(board_name, countPosts()))
    upload=("""<div class="upload"><form action="/upload" method="post" enctype="multipart/form-data" target="_self">
    <h2>New post</h2>
    <input maxlength="10" type="text" id="nickname" name="nickname" placeholder="nickname">
    <input type="file" name="image" id="image">
    <input type="submit" id="submit" value="Submit" name="submit"></form></div>""")
    image_list=("""<div style="padding: 25px 24px;">{}</div>""".format(readImageCache()))
    meta_e = meta.encode(charmap)
    heading_e = heading.encode(charmap)
    upload_e = upload.encode(charmap)
    image_list_e = image_list.encode(charmap)
    complete_page=(meta_e + heading_e + br + upload_e + image_list_e)

hp = homepage() # home page

class ReqHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(hp.complete_page) # serve the homepage
    
    def do_POST(self): # https://pymotw.com/3/http.server/
        form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST', 'CONTENT_TYPE': self.headers['Content-Type']})
        self.send_response(200)
        self.send_header('Content-Type','text/plain; charset=utf-8')
        self.end_headers()
        out = io.TextIOWrapper(self.wfile, encoding=charmap, line_buffering=False, write_through=True)
        for field in form.keys():
            field_item = form[field]
            if field_item.filename:
                file_data = field_item.file.read()
                file_len = len(file_data)
                trip_code = tripcode(ip=(self.client_address[0]), name=(str(form["nickname"])[32:-2]))
                filename = generateFilename(10)
                with open((image_dir + filename), "wb") as f:
                    f.write(file_data)
                    f.close()
                log.insert({"tripcode": "{}".format(trip_code), "upload_time": "{}".format(datetime.now()), "filename": "{}".format(filename)})
                del file_data
                out.write("Uploaded {} as {!r} ({} bytes)\n".format(field, field_item.filename, file_len))
            else:
                self.send_error(400, message="Nothing to upload")
        out.detach()
        restart()

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
httpServer = ThreadingHTTPServer((address, port), ReqHandler)

try:
    purgeImageCache()
    os.chdir(".")
    print("Working directory: " + os.getcwd())
    os.chdir(image_dir)
    print("Image directory: " + os.getcwd())
    os.chdir("..")
    print("Starting imgboard server, stop with ^C")
    httpServer.serve_forever()
except KeyboardInterrupt: # handle Ctrl-C interrupts
    print("(t)erminate or (r)estart: ")
    opt = input("")
    if opt[:1] == "t":
        print("Terminating...")
        purgeImageCache()
        httpServer.server_close()
        sys.exit()
    if opt[:1] == "r":
        print("Restarting...")
        os.execv(sys.executable, ['sudo python3'] + sys.argv)