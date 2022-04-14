import os, glob
import numpy as np
from . import guiparts
from facemap import roi, utils
from natsort import natsorted
import pickle
from PyQt5.QtWidgets import QFileDialog, QMessageBox


def open_file(parent, file_name=None):
    if file_name is None:
        file_name = QFileDialog.getOpenFileName(
            parent,
            "Open movie file",
            "",
            "Movie files (*.h5 *.mj2 *.mp4 *.mkv *.avi *.mpeg *.mpg *.asf *m4v)",
        )
    # load ops in same folder
    if file_name:
        parent.filelist = [[file_name[0]]]
        load_movies(parent)
    else:
        return None


def open_folder(parent, folder_name=None):
    if folder_name is None:
        folder_name = QFileDialog.getExistingDirectory(
            parent, "Choose folder with movies"
        )
    # load ops in same folder
    if folder_name:
        extensions = ["*.mj2", "*.mp4", "*.mkv", "*.avi", "*.mpeg", "*.mpg", "*.asf"]
        file_name = []
        for extension in extensions:
            files = glob.glob(folder_name + "/" + extension)
            files = [folder_name + "/" + os.path.split(f)[-1] for f in files]
            file_name.extend(files)
        for folder in glob.glob(folder_name + "/*/"):
            for extension in extensions:
                files = glob.glob(os.path.join(folder_name, folder, extension))
                files = [
                    folder_name + "/" + folder + "/" + os.path.split(f)[-1]
                    for f in files
                ]
                file_name.extend(files)
        if len(file_name) > 1:
            choose_files(parent, file_name)
            load_movies(parent)


def choose_files(parent, file_name):
    parent.filelist = file_name
    LC = guiparts.ListChooser("Choose movies", parent)
    result = LC.exec_()
    if len(parent.filelist) == 0:
        parent.filelist = file_name
    parent.filelist = natsorted(parent.filelist)
    if len(parent.filelist) > 1:
        dm = QMessageBox.question(
            parent,
            "multiple videos found",
            "are you processing multiple videos taken simultaneously?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if dm == QMessageBox.Yes:
            print("multi camera view")
            # expects first 4 letters to be different e.g. cam0, cam1, ...
            files = []
            iview = [os.path.basename(parent.filelist[0])[:4]]
            for f in parent.filelist[1:]:
                fbeg = os.path.basename(f)[:4]
                inview = np.array([iv == fbeg for iv in iview])
                if inview.sum() == 0:
                    iview.append(fbeg)
            print(iview)
            for k in range(len(iview)):
                ij = 0
                for f in parent.filelist:
                    if iview[k] == os.path.basename(f)[:4]:
                        if k == 0:
                            files.append([])
                        files[ij].append(f)
                        ij += 1
            parent.filelist = files
        else:
            print("single camera")
            files = parent.filelist.copy()
            parent.filelist = []
            for f in files:
                parent.filelist.append([f])

    else:
        parent.filelist = [parent.filelist]
    parent.filelist = natsorted(parent.filelist)


def open_proc(parent, file_name=None):
    if file_name is None:
        file_name = QFileDialog.getOpenFileName(
            parent, "Open processed file", filter="*.npy"
        )
        file_name = file_name[0]
    try:
        proc = np.load(file_name, allow_pickle=True).item()
        parent.filenames = proc["filenames"]
        good = True
    except:
        good = False
        print("ERROR: not a processed movie file")
    if good:
        v = []
        good = load_movies(parent, filelist=parent.filenames)
        if good:
            if "fullSVD" in proc:
                parent.fullSVD = proc["fullSVD"]
            else:
                parent.fullSVD = True
            k = 0  # number of processed things
            parent.proctype = [0, 0, 0, 0, 0, 0, 0, 0]
            parent.wroi = [0, 0, 0, 0, 0, 0, 0, 0]

            if "motSVD" in proc:
                parent.processed = True
            else:
                parent.processed = False

            iROI = 0
            parent.typestr = ["pupil", "motSVD", "blink", "run"]
            if parent.processed:
                parent.col = []
                if parent.fullSVD:
                    parent.cbs1[k].setText("fullSVD")
                    parent.cbs2[k].setText("fullSVD")
                    parent.lbls[k].setText("fullSVD")
                    parent.lbls[k].setStyleSheet("color: white;")
                    parent.proctype[0] = 0
                    parent.col.append((255, 255, 255))
                    k += 1
                parent.motSVDs = proc["motSVD"]
                parent.running = proc["running"]
                parent.pupil = proc["pupil"]
                parent.blink = proc["blink"]
            else:
                k = 0

            kt = [0, 0, 0, 0]
            # whether or not you can move the ROIs
            moveable = not parent.processed
            if proc["rois"] is not None:
                for r in proc["rois"]:
                    dy = r["yrange"][-1] - r["yrange"][0]
                    dx = r["xrange"][-1] - r["xrange"][0]
                    pos = [
                        r["yrange"][0] + parent.sy[r["ivid"]],
                        r["xrange"][0] + parent.sx[r["ivid"]],
                        dy,
                        dx,
                    ]
                    parent.saturation.append(r["saturation"])
                    parent.rROI.append([])
                    parent.reflectors.append([])
                    if "pupil_sigma" in r:
                        psig = r["pupil_sigma"]
                        parent.pupil_sigma = psig
                        parent.sigmaBox.setText(str(r["pupil_sigma"]))
                    else:
                        psig = None
                    parent.ROIs.append(
                        roi.sROI(
                            rind=r["rind"],
                            rtype=r["rtype"],
                            iROI=r["iROI"],
                            color=r["color"],
                            moveable=moveable,
                            parent=parent,
                            saturation=r["saturation"],
                            pupil_sigma=psig,
                            yrange=r["yrange"],
                            xrange=r["xrange"],
                            pos=pos,
                            ivid=r["ivid"],
                        )
                    )
                    if "reflector" in r:
                        for i, rr in enumerate(r["reflector"]):
                            pos = [
                                rr["yrange"][0],
                                rr["xrange"][0],
                                rr["yrange"][-1] - rr["yrange"][0],
                                rr["xrange"][-1] - rr["xrange"][0],
                            ]
                            parent.rROI[-1].append(
                                roi.reflectROI(
                                    iROI=r["iROI"],
                                    wROI=i,
                                    pos=pos,
                                    parent=parent,
                                    yrange=rr["yrange"],
                                    xrange=rr["xrange"],
                                    ellipse=rr["ellipse"],
                                )
                            )
                    if parent.fullSVD:
                        parent.iROI = k - 1
                    else:
                        parent.iROI = k
                    parent.ROIs[-1].ellipse = r["ellipse"]
                    parent.sl[1].setValue(
                        int(parent.saturation[parent.iROI] * 100 / 255)
                    )
                    parent.ROIs[parent.iROI].plot(parent)
                    if parent.processed:
                        if k < 5:
                            parent.cbs1[k].setText(
                                "%s%d" % (parent.typestr[r["rind"]], kt[r["rind"]])
                            )
                            parent.cbs2[k].setText(
                                "%s%d" % (parent.typestr[r["rind"]], kt[r["rind"]])
                            )
                            parent.lbls[k].setText(
                                "%s%d" % (parent.typestr[r["rind"]], kt[r["rind"]])
                            )
                            parent.lbls[k].setStyleSheet(
                                "color: rgb(%s,%s,%s);"
                                % (
                                    str(int(r["color"][0])),
                                    str(int(r["color"][1])),
                                    str(int(r["color"][2])),
                                )
                            )
                            parent.wroi[k] = kt[r["rind"]]
                            kt[r["rind"]] += 1
                            parent.proctype[k] = r["rind"] + 1
                            parent.col.append(r["color"])
                    k += 1
            parent.kroi = k

            # initialize plot
            parent.cframe = 1
            if parent.processed:
                for k in range(parent.kroi):
                    parent.cbs1[k].setEnabled(True)
                    parent.cbs2[k].setEnabled(True)
                if parent.fullSVD:
                    parent.cbs1[0].setEnabled(True)
                    parent.cbs1[0].setChecked(True)
                    parent.cbs2[0].setEnabled(True)
                parent.plot_processed()
            parent.next_frame()


def get_folder_path(parent):
    # Open a file dialog to select a folder
    path = QFileDialog.getExistingDirectory(parent, "Select a folder")
    # Check if path exists
    if path:
        return path
    else:
        # Open a qmessagebox to inform the user that the path does not exist
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setText("The path does not exist")
        msg.setWindowTitle("Warning")
        msg.exec_()
        return None


def load_movies(parent, filelist=None):
    if filelist is not None:
        parent.filelist = filelist
    try:
        cumframes, Ly, Lx, containers = utils.get_frame_details(parent.filelist)
        nframes = cumframes[-1]
        good = True
    except Exception as e:
        print("ERROR: not a supported movie file")
        print(e)
        good = False
    if good:
        parent.reset()
        parent.video = containers
        parent.filenames = parent.filelist
        parent.nframes = nframes
        parent.cumframes = np.array(cumframes).astype(int)
        parent.Ly = Ly
        parent.Lx = Lx
        parent.p1.clear()
        parent.p2.clear()
        if len(parent.Ly) < 2:
            parent.LY = parent.Ly[0]
            parent.LX = parent.Lx[0]
            parent.sx = np.array([int(0)])
            parent.sy = np.array([int(0)])
            parent.vmap = np.zeros((parent.LY, parent.LX), np.int32)
        else:
            # make placement of movies
            Ly = np.array(parent.Ly.copy())
            Lx = np.array(parent.Lx.copy())

            LY, LX, sy, sx = utils.video_placement(Ly, Lx)
            parent.vmap = -1 * np.ones((LY, LX), np.int32)
            for i in range(Ly.size):
                parent.vmap[sy[i] : sy[i] + Ly[i], sx[i] : sx[i] + Lx[i]] = i
            parent.sy = sy
            parent.sx = sx
            parent.LY = LY
            parent.LX = LX

        parent.fullimg = np.zeros((parent.LY, parent.LX, 3))
        parent.imgs = []
        parent.img = []
        for i in range(len(parent.Ly)):
            parent.imgs.append(np.zeros((parent.Ly[i], parent.Lx[i], 3, 3)))
            parent.img.append(np.zeros((parent.Ly[i], parent.Lx[i], 3)))
        # parent.movieLabel.setText(os.path.dirname(parent.filenames[0][0]))
        parent.save_path = os.path.dirname(parent.filenames[0][0])
        parent.frameDelta = int(np.maximum(5, parent.nframes / 200))
        parent.frameSlider.setSingleStep(parent.frameDelta)
        if parent.nframes > 0:
            parent.update_frame_slider()
            parent.update_buttons()
        parent.cframe = 1
        parent.loaded = True
        parent.processed = False
        parent.jump_to_frame()
    return good


def save_folder(parent):
    folderName = QFileDialog.getExistingDirectory(parent, "Choose save folder")
    # load ops in same folder
    if folderName:
        parent.save_path = folderName
        if len(folderName) > 30:
            parent.savelabel.setText("..." + folderName[-30:])
        else:
            parent.savelabel.setText(folderName)


def get_pose_file(parent):
    # Open a folder and allow selection of multiple files with extension *.h5 only
    # Returns a list of files
    filelist = []
    filelist = QFileDialog.getOpenFileNames(
        parent, "Open Pose File", parent.save_path, "*.h5"
    )
    if filelist[0] == "":
        return
    else:
        parent.poseFilepath = natsorted(filelist[0])
        parent.poseFileLoaded = True
        parent.load_labels()
        parent.Labels_checkBox.setChecked(True)
        parent.update_status_bar("Pose file(s) loaded")


def load_cluster_labels(parent):
    try:
        file_name = QFileDialog.getOpenFileName(
            parent,
            "Select cluster labels file",
            "",
            "Cluster label files (*.npy *.pkl)",
        )[0]
        extension = file_name.split(".")[-1]
        if extension == "npy":
            parent.loaded_cluster_labels = np.load(file_name, allow_pickle=True)
            parent.is_cluster_labels_loaded = True
        elif extension == "pkl":
            with open(file_name, "rb") as f:
                parent.loaded_cluster_labels = pickle.load(f)
                parent.is_cluster_labels_loaded = True
        else:
            return
    except Exception as e:
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Error: not a supported filetype")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        print(e)


def get_pose_model_filepath(parent):
    # Open a file dialog to select a model file
    model_file = QFileDialog.getOpenFileName(
        parent, "Select model file", "", "model files (*.pt)"
    )[0]
    if model_file:
        return model_file
    else:
        return None


def load_umap(parent):
    try:
        file_name = QFileDialog.getOpenFileName(
            parent, "Select UMAP data file", "", "UMAP label files (*.npy *.pkl)"
        )[0]
        extension = file_name.split(".")[-1]
        if extension == "npy":
            embedded_data = np.load(file_name, allow_pickle=True)
        elif extension == "pkl":
            with open(file_name, "rb") as f:
                embedded_data = pickle.load(f)
        else:
            return
        return embedded_data
    except Exception as e:
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Error: not a supported filetype")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        print(e)


def load_trace_data(parent):
    try:
        file_name = QFileDialog.getOpenFileName(
            parent, "Select data file", "", "(*.npy *.pkl)"
        )[0]
        extension = file_name.split(".")[-1]
        if extension == "npy":
            dat = np.load(file_name, allow_pickle=True)
        elif extension == "pkl":
            with open(file_name, "rb") as f:
                dat = pickle.load(f)
        else:
            return
        return dat
    except Exception as e:
        msg = QMessageBox(parent)
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Error: not a supported filetype")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
        print(e)


def save_clustering_output(output, parent):
    filename, ext = parent.filenames[0][0].split(".")
    filename = filename.split("/")[-1]  # Use video filename
    savename = os.path.join(parent.save_path, ("%s_facemap_clusters.npy" % filename))
    np.save(savename, output)
    parent.update_status_bar("Clustering output saved: " + savename)
