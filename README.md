[![Downloads](https://pepy.tech/badge/facemap)](https://pepy.tech/project/facemap)
[![Downloads](https://pepy.tech/badge/facemap/month)](https://pepy.tech/project/facemap)
[![GitHub stars](https://badgen.net/github/stars/Mouseland/facemap)](https://github.com/MouseLand/facemap/stargazers)
[![GitHub forks](https://badgen.net/github/forks/Mouseland/facemap)](https://github.com/MouseLand/facemap/network/members)
[![](https://img.shields.io/github/license/MouseLand/facemap)](https://github.com/MouseLand/facemap/blob/main/LICENSE)
[![PyPI version](https://badge.fury.io/py/facemap.svg)](https://badge.fury.io/py/facemap)
[![Documentation Status](https://readthedocs.org/projects/ansicolortags/badge/?version=latest)](https://pypi.org/project/facemap/)
[![GitHub open issues](https://badgen.net/github/open-issues/Mouseland/facemap)](https://github.com/MouseLand/facemap/issues)

# Facemap <img src="facemap/mouse.png" width="200" title="lilmouse" alt="lilmouse" align="right" vspace = "50">

Facemap is a framework for predicting neural activity from mouse orofacial movements. It includes a pose estimation model for tracking distinct keypoints on the mouse face, a neural network model for predicting neural activity using the pose estimates, and also can be used compute the singular value decomposition (SVD) of behavioral videos.

To learn about Facemap, read the [paper](https://www.biorxiv.org/content/10.1101/2022.11.03.515121v1) or check out the tweet [thread](https://twitter.com/Atika_Ibrahim/status/1588885329951367168?s=20&t=AhE3vBTnCvW36QiTyhu0qQ). For support, please open an [issue](https://github.com/MouseLand/facemap/issues).

### CITATION

**If you use Facemap, please cite the Facemap [paper](https://www.biorxiv.org/content/10.1101/2022.11.03.515121v1):**  
Syeda, A., Zhong, L., Tung, R., Long, W., Pachitariu, M.\*, & Stringer, C.\* (2022). Facemap: a framework for modeling neural activity based on orofacial tracking. <em>bioRxiv</em>.
[[bibtex](https://scholar.googleusercontent.com/scholar.bib?q=info:ckbIvC5D_FsJ:scholar.google.com/&output=citation&scisdr=CgXHFLYtEMb9qP1BWD0:AAGBfm0AAAAAY3JHQD2D6ewMN1lsoTB4rVT_uLVYr8DU&scisig=AAGBfm0AAAAAY3JHQOtGw17323ZXomLmlJoieZSXitl2&scisf=4&ct=citation&cd=-1&hl=en&scfhb=1)]

**If you use the SVD computation or pupil tracking components, please also cite our previous [paper](https://www.nature.com/articles/s41592-022-01663-4):**  
Stringer, C.\*, Pachitariu, M.\*, Steinmetz, N., Reddy, C. B., Carandini, M., & Harris, K. D. (2019). Spontaneous behaviors drive multidimensional, brainwide activity. <em>Science, 364</em>(6437), eaav7893.
[[bibtex](https://scholar.googleusercontent.com/scholar.bib?q=info:DNVOkEas4K8J:scholar.google.com/&output=citation&scisdr=CgXHFLYtEMb9qP1Bt0Q:AAGBfm0AAAAAY3JHr0TJourtY6W2vbjy7opKXX2jOX9Z&scisig=AAGBfm0AAAAAY3JHryiZnvgWM1ySwd_xQ9brvQxH71UM&scisf=4&ct=citation&cd=-1&hl=en&scfhb=1)]

## Installation

If you have an older `facemap` environment you can remove it with `conda env remove -n facemap` before creating a new one.

If you are using a GPU, make sure its drivers and the cuda libraries are correctly installed.

1. Install an [Anaconda](https://www.anaconda.com/products/distribution) distribution of Python. Note you might need to use an anaconda prompt if you did not add anaconda to the path.
2. Open an anaconda prompt / command prompt which has `conda` for **python 3** in the path
3. Create a new environment with `conda create --name facemap python=3.8`. We recommend python 3.8, but python 3.9 and 3.10 will likely work as well.
4. To activate this new environment, run `conda activate facemap`
5. To install the minimal version of facemap, run `python -m pip install facemap`.  
6. To install facemap and the GUI, run `python -m pip install facemap[gui]`. If you're on a zsh server, you may need to use ' ' around the facemap[gui] call: `python -m pip install 'facemap[gui]'.

To upgrade facemap (package [here](https://pypi.org/project/facemap/)), run the following in the environment:

~~~sh
python -m pip install facemap --upgrade
~~~

Note you will always have to run `conda activate facemap` before you run facemap. If you want to run jupyter notebooks in this environment, then also `pip install notebook` and `python -m pip install matplotlib`.

You can also try to install facemap and the GUI dependencies from your base environment using the command

~~~~sh
python -m pip install facemap[gui]
~~~~

If you have **issues** with installation, see the [docs](https://github.com/MouseLand/facemap/blob/dev/docs/installation.md) for more details. You can also use the facemap environment file included in the repository and create a facemap environment with `conda env create -f environment.yml` which may solve certain dependency issues.

If these suggestions fail, open an issue.

### GPU version (CUDA) on Windows or Linux

If you plan on running many images, you may want to install a GPU version of *torch* (if it isn't already installed).

Before installing the GPU version, remove the CPU version:
~~~
pip uninstall torch
~~~

Follow the instructions [here](https://pytorch.org/get-started/locally/) to determine what version to install. The Anaconda install is strongly recommended, and then choose the CUDA version that is supported by your GPU (newer GPUs may need newer CUDA versions > 10.2). For instance this command will install the 11.3 version on Linux and Windows (note the `torchvision` and `torchaudio` commands are removed because facemap doesn't require them):

~~~
conda install pytorch==1.12.1 cudatoolkit=11.3 -c pytorch
~~~~

and this will install the 11.7 toolkit

~~~
conda install pytorch pytorch-cuda=11.7 -c pytorch
~~~

## Supported videos
Facemap supports grayscale and RGB movies. The software can process multi-camera videos for pose tracking and SVD analysis. Please see [example movies](https://drive.google.com/open?id=1cRWCDl8jxWToz50dCX1Op-dHcAC-ttto) for testing the GUI. Movie file extensions supported include:

'.mj2','.mp4','.mkv','.avi','.mpeg','.mpg','.asf'

For more details, please refer to the [data acquisition page](docs/data_acquisition.md).


# I. Pose tracking

<img src="figs/facemap.gif" width="100%" height="500" title="Tracker" alt="tracker" algin="middle" vspace = "10">

Facemap provides a trained network for tracking distinct keypoints on the mouse face from different camera views (some examples shown below). The process for tracking keypoints is as follows:
 1. Load video. (Optional) Use the file menu to set output folder.
 2. Click `process` (Note: check `keypoints` for this step).
 3. Select bounding box to focus on the face as shown below.
 4. The processed keypoints `*.h5` file will be saved in the output folder along with the corresponding metadata file `*.pkl`.

Keypoints will be predicted in the selected bounding box region so please ensure the bounding box focuses on the face. See example frames [here](figs/mouse_views.png). 


For more details on using the tracker, please refer to the [GUI Instructions](docs/pose_tracking_gui_tutorial.md). See  [command line interface (CLI) instructions](docs/pose_tracking_cli_tutorial.md) and for more examples, please see [tutorial notebooks](https://github.com/MouseLand/facemap/tree/dev/notebooks).

<p float="middle">
<img src="figs/mouse_face1_keypoints.png"  width="310" height="290" title="View 1" alt="view1" align="left" vspace = "10" hspace="30" style="border: 0.5px solid white"  />
<img src="figs/mouse_face0_keypoints.png" width="310" height="290" title="View 2" alt="view2" algin="right" vspace = "10" style="border: 0.5px solid white">
</p>


### :mega: User contributions :video_camera: :camera: 
Facemap aims to provide a simple and easy-to-use tool for tracking mouse orofacial movements. The tracker's performance for new datasets could be further improved by expand our training set. You can contribute to the model by sharing videos/frames on the following email address(es): `asyeda1[at]jh.edu` or `stringerc[at]janelia.hhmi.org`.

### Support

For any issues or questions about Facemap, please [open an issue](https://github.com/MouseLand/facemap/issues).


# II. Neural activity prediction

Facemap includes a deep neural network encoder for predicting neural activity or principal components of neural activity from mouse orofacial pose estimates extracted using the tracker. The process for neural activity prediction is as follows:
 1. Load video. (Optional) Use the file menu to set output folder.
 2. Load or process keypoints for the video.
 3. Load neural activity data (optional) and timestamps for behavioral and neural data.
 4. Run neural activity prediction (Note: Use help section to set training parameters for the model).
 5. The predicted neural activity `*.npy` file will be saved in the selected output folder.

 Please see neural activity prediction [tutorial](docs/neural_activity_prediction_tutorial.md) for more details.


# III. SVD processing

Facemap provides options for singular value decomposition (SVD) of single and multi-camera videos. SVD analysis can be performed across static frames called movie SVD (`movSVD`) to extract the spatial components or over the difference between consecutive frames called motion SVD (`motSVD`) to extract the temporal components of the video. The first 500 principal components from SVD analysis are saved as output along with other variables. For more details, see [python tutorial](docs/svd_python_tutorial.md). The process for SVD analysis is as follows:
 1. Load video. (Optional) Use the file menu to set output folder.
 2. Click `process` (Note: check `motSVD`  or `movSVD` for this step).
 3. The processed SVD `*_proc.npy` (and `*_proc.mat`) file will be saved in the output folder selected.

### [*HOW TO GUI* (Python)](docs/svd_python_tutorial.md)

([video](https://www.youtube.com/watch?v=Rq8fEQ-DOm4) with old install instructions)

<img src="figs/face_fast.gif" width="100%" alt="face gif">

Run the following command in a terminal
```
python -m facemap
```
Default starting folder is set to wherever you run `python -m FaceMap`


### [*HOW TO GUI* (MATLAB)](docs/svd_matlab_tutorial.md)

To start the GUI, run the command `MovieGUI` in this folder. The following window should appear. After you click an ROI button and draw an area, you have to **double-click** inside the drawn box to confirm it. To compute the SVD across multiple simultaneously acquired videos you need to use the "multivideo SVD" options to draw ROI's on each video one at a time.

<div align="center">
<img src="figs/GUIscreenshot.png" width="80%" alt="gui screenshot" >
</div>

