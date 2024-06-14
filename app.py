from flask import Flask, redirect, request, render_template, session, url_for
import os
from datetime import datetime
import instaloader
import atexit
import shutil
import cv2
import numpy as np
from sklearn.cluster import KMeans
import os



# configure application
app = Flask(__name__)
app.secret_key = os.urandom(24) # secret key for session
if __name__ == '__main__':
    app.run(debug=True)

# get instaloader instance
ig = instaloader.Instaloader()

profile_directory = 'user_profile/'
pfp_directory = 'static/pfp_directory/'
entries = os.listdir(profile_directory)

#atexit function referenced by chatGPT
# registers atexit function, will be called when program exits (stops)
def register_delete_directory_contents(profile_directory):    
    atexit.register(delete_directory_contents, profile_directory)

# deletes user_profile contents
def delete_directory_contents(profile_directory):
    if os.path.exists(profile_directory):
        for entry in entries:
            entry_path = os.path.join(profile_directory, entry)
            if os.path.isfile(entry_path):
                os.remove(entry_path)
            else:
                shutil.rmtree(entry_path)

# deletes stuff when program starts up
register_delete_directory_contents(profile_directory)
register_delete_directory_contents(pfp_directory)

# global error messages
def set_error_message(message):
    session['error_message'] = message

def get_error_message():
    return session.pop('error_message', '')

# main page
@app.route("/")
def index():
    error_message = get_error_message()
    profile = session.get('profile', '')
    datefrom = session.get('datefrom', '')
    dateto = session.get('dateto', '')
    return render_template("index.html", error=error_message, profile=profile, datefrom=datefrom, dateto=dateto)

@app.route("/redirect", methods=["POST"])
def handle_redirect():
    # check for username
    set_error_message("")
    profile = request.form.get("profile")
    datefrom = request.form.get("datefrom")
    dateto = request.form.get("dateto")
    print(profile, datefrom, dateto) # console checking if works

    # saves inputs to session incase of submission error
    session['profile'] = profile
    session['datefrom'] = datefrom
    session['dateto'] = dateto
    if not profile:
        set_error_message("username required")
        return redirect('/')
    elif not datefrom:
        set_error_message("date from required")
        return redirect('/')
    elif not dateto:
        set_error_message("date to required")
        return redirect('/')
    try:
        # try downloading profile data
        posts = instaloader.Profile.from_username(ig.context, profile).get_posts()
        # state the target path where to download data
        target_path = os.path.join(os.getcwd())
        os.makedirs(target_path, exist_ok=True)
        
        # download the profile's image posts to the target path
        existing_directory = 'user_profile/' + profile
        ig.dirname_pattern = existing_directory

        # doesn't save metadata, and downloads pics
        ig.save_metadata = False
        ig.download_pictures = True
        ig.download_comments = False
        ig.download_videos = False
        
        # downloads posts from time frame
        SINCE = datetime.strptime(datefrom, '%Y-%m-%d')
        UNTIL = datetime.strptime(dateto, '%Y-%m-%d')

        for post in posts:
            postdate = post.date

            if postdate > UNTIL:
                continue
            elif postdate < SINCE:
                continue
            else:
                ig.download_post(post, profile)

        ig.download_profile(profile, profile_pic_only = True)
    
        # delete any files that aren't image type or IGNORE, DELETE AFTER SESSION OVER
        for file in os.listdir(existing_directory):
            if file.endswith(".txt"):
                os.remove(os.path.join(existing_directory, file))    

        # return result
        return redirect(url_for('result', profile=profile))
    except Exception as e:
        # in case any unusual error
        app.logger.error(f"An unexpected error occured: {e}")
        return redirect('/')

@app.route('/result/<profile>')
def result(profile):
    profile = session.get('profile', None)
    if profile is None:
        return redirect('/')
    
    # GETS 5 DOMINANT COLORS, referenced from chatGPT
    directory = 'user_profile/' + profile
    images, pfp_path = load_images_from_directory(directory)
    dominant_colors = aggregate_colors(images, k=5, final_k=5)
    dominant_colors_list = dominant_colors.tolist()

    # Display the dominant colors in terminal
    for i, color in enumerate(dominant_colors):
        print(f"Color {i+1}: {color}")
    print(images)
    print(pfp_path)

    pfp_url = url_for('static', filename=f'pfp_directory/{os.path.basename(pfp_path)}')
    print(pfp_url)
    return render_template("result.html", profile=profile, dominant_colors=dominant_colors_list, pfp_url=pfp_url)


def get_dominant_colors(image, k=5):
    # Reshape the image to be a list of pixels
    # turns image into 2d array instead of 3d (height, width, rgb channels)
    pixels = image.reshape(-1, 3)
    
    # Perform KMeans clustering to find the k dominant colors
    # groups the pixels together in k (5) clusters
    kmeans = KMeans(n_clusters=k)
    kmeans.fit(pixels)
    
    # Get the cluster centers (dominant colors)
    dominant_colors = kmeans.cluster_centers_
    
    # Convert to integer (0-255) values
    dominant_colors = np.array(dominant_colors, dtype='uint8')
    
    return dominant_colors

def aggregate_colors(images, k=5, final_k=5):
    all_colors = []

    # Extract dominant colors from each image
    for image in images:
        colors = get_dominant_colors(image, k=k)
        all_colors.extend(colors)

    # Perform KMeans clustering again on the aggregated colors
    kmeans = KMeans(n_clusters=final_k)
    kmeans.fit(all_colors)

    # Get the final dominant colors
    final_colors = kmeans.cluster_centers_

    # Convert to integer (0-255) values
    final_colors = np.array(final_colors, dtype='uint8')

    return final_colors

def load_images_from_directory(directory):
    images = []
    pfp_path = None

    for filename in os.listdir(directory):
        if filename.lower().endswith('profile_pic.jpg'):
            src_path = os.path.join(directory, filename)
            pfp_path = os.path.join(pfp_directory, filename)
            shutil.move(src_path, pfp_path)
        elif filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            image_path = os.path.join(directory, filename)
            image = cv2.imread(image_path)
            if image is not None:
                images.append(image)
    return images, pfp_path
