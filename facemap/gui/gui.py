import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyqtgraph as pg
from matplotlib import cm
from matplotlib import colors as mpl_colors
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtGui import QFont, QIcon, QPainterPath
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDesktopWidget,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStatusBar,
    QToolButton,
    QWidget,
)
from scipy.stats import skew, zscore

from facemap import cluster, neural_activity, process, roi, utils
from facemap.pose import pose_gui, refine_pose
from facemap.pose import pose

from . import guiparts, io, menus

istr = ["pupil", "motSVD", "blink", "running", "movSVD"]


class MainW(QtWidgets.QMainWindow):
    def __init__(self, moviefile=None, savedir=None):
        super(MainW, self).__init__()
        icon_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)), "../mouse.png"
        )
        app_icon = QIcon()
        app_icon.addFile(icon_path, QtCore.QSize(16, 16))
        app_icon.addFile(icon_path, QtCore.QSize(24, 24))
        app_icon.addFile(icon_path, QtCore.QSize(32, 32))
        app_icon.addFile(icon_path, QtCore.QSize(48, 48))
        app_icon.addFile(icon_path, QtCore.QSize(96, 96))
        app_icon.addFile(icon_path, QtCore.QSize(256, 256))
        self.setWindowIcon(app_icon)

        pg.setConfigOptions(imageAxisOrder="row-major")
        self.setGeometry(15, 15, 1470, 1000)
        self.setWindowTitle("Facemap")
        self.setStyleSheet("QMainWindow {background: 'black';}")
        self.styleUnpressed = (
            "QPushButton {Text-align: left; "
            "background-color: rgb(50,50,50); "
            "color:white;}"
        )
        self.stylePressed = (
            "QPushButton {Text-align: left; "
            "background-color: rgb(100,50,100); "
            "color:white;}"
        )
        self.styleInactive = (
            "QPushButton {Text-align: left; "
            "background-color: rgb(50,50,50); "
            "color:gray;}"
        )

        try:
            # try to load user settings
            opsfile = os.path.join(
                os.path.abspath(os.path.dirname(__file__)), "ops_user.npy"
            )
            self.ops = np.load(opsfile, allow_pickle=True).item()
        except:
            self.ops = {
                "sbin": 4,
                "pupil_sigma": 2.0,
                "fullSVD": False,
                "save_path": "",
                "save_mat": False,
            }

        self.save_path = self.ops["save_path"]

        menus.mainmenu(self)
        self.online_mode = False
        # menus.onlinemenu(self)

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.scene_grid_layout = QGridLayout()
        self.central_widget.setLayout(self.scene_grid_layout)
        # --- cells image
        self.sizeObject = QDesktopWidget().screenGeometry(-1)
        self.resize(self.sizeObject.width(), self.sizeObject.height())

        self.video_window = pg.GraphicsLayoutWidget()
        self.video_window.move(self.sizeObject.height(), self.sizeObject.width())
        self.video_window.resize(self.sizeObject.height(), self.sizeObject.width())
        self.scene_grid_layout.addWidget(self.video_window, 0, 2, 10, 7)

        # Create a window for embedding and ROI plot
        self.roi_embed_window = pg.GraphicsLayoutWidget()
        self.roi_embed_window.move(self.sizeObject.height(), 0)
        self.roi_embed_window.resize(self.sizeObject.height(), self.sizeObject.width())
        self.scene_grid_layout.addWidget(self.roi_embed_window, 13, 2, 12, 7)

        # Create a window for plots
        self.plots_window = pg.GraphicsLayoutWidget()
        self.scene_grid_layout.addWidget(self.plots_window, 1, 9, 24, 8)

        # Add logo
        # icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "mouse.png")
        # self.logo = QPixmap(icon_path).scaled(90, 70, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        # self.logoLabel = QtGui.QLabel(self)
        # self.logoLabel.setPixmap(self.logo)
        # self.logoLabel.setScaledContents(True)
        # self.scene_grid_layout.addWidget(self.logoLabel,0,0,3,2)

        # A plot area (ViewBox + axes) for displaying the image
        self.p0 = self.video_window.addViewBox(
            lockAspect=True, row=0, col=0, rowspan=2, invertY=True
        )
        self.p0.setMenuEnabled(False)
        self.pimg = pg.ImageItem()
        self.p0.addItem(self.pimg)

        # image ROI
        self.pROI = self.roi_embed_window.addViewBox(
            lockAspect=True, row=2, col=0, rowspan=2, invertY=True
        )
        # Set size of pROI to be the same as p0
        self.pROI.setGeometry(self.p0.sceneBoundingRect())
        self.pROI.setMenuEnabled(False)
        self.pROIimg = pg.ImageItem()
        self.pROI.addItem(self.pROIimg)
        self.scatter = pg.ScatterPlotItem([0], [0], pen="k", symbol="+")
        self.pROI.addItem(self.scatter)

        # roi initializations
        self.iROI = 0
        self.nROIs = 0
        self.saturation = []
        self.ROIs = []

        # Saturation groupbox
        self.saturation_groupbox = QGroupBox()
        self.saturation_groupbox.setStyleSheet(
            "QGroupBox { border: 0px solid white; border-style: outset;}"
        )
        self.saturation_groupbox.setLayout(QGridLayout())

        # saturation sliders
        self.saturation_sliders = []
        self.sat = [255, 255]

        qlabel = QLabel("Saturation:")
        qlabel.setStyleSheet("color: white;")
        self.saturation_groupbox.layout().addWidget(qlabel, 0, 0)
        video_saturation_slider = guiparts.Slider(0, self)
        self.saturation_sliders.append(video_saturation_slider)
        self.saturation_groupbox.layout().addWidget(self.saturation_sliders[0], 1, 0)

        # Add label to indicate saturation level
        self.saturation_level_label = QLabel(str(self.saturation_sliders[0].value()))
        self.saturation_level_label.setStyleSheet("color: white;")
        # self.scene_grid_layout.addWidget(self.saturation_level_label, 0, 5, 1, 1)

        # Reflector
        self.reflector = QPushButton("Add corneal reflection")
        self.reflector.setEnabled(False)
        self.reflector.clicked.connect(self.add_reflectROI)
        self.rROI = []
        self.reflectors = []
        self.scene_grid_layout.addWidget(self.reflector, 0, 6, 1, 1)

        # roi Saturation groupbox
        self.roi_saturation_groupbox = QGroupBox()
        self.roi_saturation_groupbox.setStyleSheet(
            "QGroupBox { border: 0px solid white; border-style: outset;}"
        )
        self.roi_saturation_groupbox.setLayout(QGridLayout())

        qlabel = QLabel("ROI Saturation:")
        qlabel.setStyleSheet("color: white;")
        self.roi_saturation_groupbox.layout().addWidget(qlabel, 0, 0)
        roi_saturation_slider = guiparts.Slider(1, self)
        self.saturation_sliders.append(roi_saturation_slider)
        self.roi_saturation_groupbox.layout().addWidget(
            self.saturation_sliders[1], 1, 0
        )

        self.roi_saturation_label = QLabel(str(self.saturation_sliders[1].value()))
        self.roi_saturation_label.setStyleSheet("color: white;")

        self.saturation_sliders[0].valueChanged.connect(self.set_saturation_label)
        self.saturation_sliders[1].valueChanged.connect(self.set_ROI_saturation_label)

        # Plots
        self.keypoints_traces_plot = self.plots_window.addPlot(
            name="keypoints_traces_plot", row=0, col=1, title="Keypoints traces"
        )
        self.keypoints_traces_plot.scene().sigMouseClicked.connect(
            self.on_click_keypoints_plot
        )
        self.keypoints_traces_plot.setMouseEnabled(x=True, y=False)
        self.keypoints_traces_plot.setMenuEnabled(False)
        self.keypoints_traces_plot.hideAxis("left")
        self.scatter1 = pg.ScatterPlotItem()
        self.keypoints_traces_plot.addItem(self.scatter1)
        self.keypoints_vtick = None
        self.keypoints_groups = ["Eye", "Nose", "Whiskers", "Mouth", "Paw"]
        self.keypoints_subgroups = [
            ["eye(back)", "eye(bottom)", "eye(front)", "eye(top)"],
            ["nose(bottom)", "nose(r)", "nose(tip)", "nose(top)", "nosebridge"],
            ["whisker(c1)", "whisker(c2)", "whisker(d1)"],
            ["lowerlip", "mouth"],
            ["paw"],
        ]

        self.svd_traces_plot = self.plots_window.addPlot(
            name="svd_traces_plot", row=1, col=1, title="SVD traces"
        )
        self.svd_traces_plot.scene().sigMouseClicked.connect(self.on_click_svd_plot)
        self.svd_traces_plot.setMouseEnabled(x=True, y=False)
        self.svd_traces_plot.setMenuEnabled(False)
        self.svd_traces_plot.hideAxis("left")
        self.scatter2 = pg.ScatterPlotItem()
        self.svd_traces_plot.addItem(self.scatter1)
        self.svd_traces_plot.setXLink("keypoints_traces_plot")
        self.svd_plot_vtick = None

        # Add third plot
        self.neural_activity_plot = self.plots_window.addPlot(
            name="neural_activity_plot", row=2, col=1, title="Neural activity"
        )
        self.neural_activity_plot.scene().sigMouseClicked.connect(
            self.on_click_neural_activity_plot
        )
        self.neural_activity_plot.setMouseEnabled(x=True, y=False)
        self.neural_activity_plot.setMenuEnabled(False)
        self.neural_activity_plot.hideAxis("left")
        self.neural_activity_plot.setXLink("keypoints_traces_plot")
        self.neural_activity_plot.disableAutoRange()
        self.neural_activity_vtick = None

        # Add fourth plot
        self.neural_predictions_plot = self.plots_window.addPlot(
            name="neural_predictions_plot", row=3, col=1, title="Neural predictions"
        )
        self.neural_predictions_plot.scene().sigMouseClicked.connect(
            self.on_click_neural_activity_plot
        )
        self.neural_predictions_plot.setMouseEnabled(x=True, y=False)
        self.neural_predictions_plot.setMenuEnabled(False)
        self.neural_predictions_plot.hideAxis("left")
        self.neural_predictions_plot.setXLink("keypoints_traces_plot")
        self.neural_predictions_plot.disableAutoRange()
        self.neural_predictions_vtick = None

        self.nframes = 0
        self.cframe = 0
        self.traces1 = None
        self.traces2 = None
        self.neural_data_loaded = False
        self.neural_predictions_loaded = False

        ## Pose plot
        self.pose_scatterplot = pg.ScatterPlotItem(hover=True)
        self.pose_scatterplot.sigClicked.connect(self.keypoints_clicked)
        self.pose_scatterplot.sigHovered.connect(self.keypoints_hovered)
        self.pose_model = None
        self.poseFilepath = []
        self.keypoints_brushes = []
        self.bbox = []
        self.bbox_set = False
        self.resize_img, self.add_padding = False, False

        self.clustering_plot = self.roi_embed_window.addPlot(
            row=2, col=0, rowspan=2, lockAspect=True, enableMouse=False
        )
        self.clustering_plot.hideAxis("left")
        self.clustering_plot.hideAxis("bottom")
        self.clustering_scatterplot = pg.ScatterPlotItem(hover=True)
        # self.clustering_scatterplot.sigClicked.connect(lambda obj, ev: self.cluster_model.highlight_embedded_point(obj, ev, parent=self))
        self.clustering_scatterplot.sigHovered.connect(
            lambda obj, ev: self.cluster_model.embedded_points_hovered(
                obj, ev, parent=self
            )
        )
        # self.clustering_plot.scene().sigMouseMoved.connect(lambda pos: self.cluster_model.mouse_moved_embedding(pos, parent=self))
        self.clustering_highlight_scatterplot = pg.ScatterPlotItem(hover=True)
        self.clustering_highlight_scatterplot.sigHovered.connect(
            lambda obj, ev: self.cluster_model.embedded_points_hovered(
                obj, ev, parent=self
            )
        )

        self.clustering_plot_legend = pg.LegendItem(
            labelTextSize="12pt", title="Cluster"
        )
        self.cluster_model = cluster.Cluster(parent=self)
        self.is_cluster_labels_loaded = False
        self.loaded_cluster_labels = None

        self.updateTimer = QtCore.QTimer()
        self.updateTimer.timeout.connect(self.next_frame)
        self.cframe = 0
        self.loaded = False
        self.wraw = False
        self.video_window.scene().sigMouseClicked.connect(self.plot_clicked)
        self.video_window.show()
        self.show()
        self.processed = False
        if moviefile is not None:
            io.load_movies(self, [[moviefile]])
        if savedir is not None:
            self.save_path = savedir
            self.savelabel.setText("..." + savedir[-20:])

        # Status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.progressBar = QProgressBar()
        self.statusBar.addPermanentWidget(self.progressBar)
        self.progressBar.setGeometry(0, 0, 300, 25)
        self.progressBar.setMaximum(100)
        self.progressBar.hide()
        self.make_buttons()

        # Create neural activity data object
        self.neural_activity = neural_activity.NeuralActivity(parent=self)
        self.neural_predictions = neural_activity.NeuralActivity(parent=self)

    def make_buttons(self):
        facemap_label = QLabel("Facemap - SVDs & Tracker")
        facemap_label.setStyleSheet("color: white;")
        facemap_label.setAlignment(QtCore.Qt.AlignCenter)
        facemap_label.setFont(QFont("Arial", 16, QFont.Bold))

        # ~~~~~~~~~~~~~~~~~~~~~~~~ SVD variables ~~~~~~~~~~~~~~~~~~~~~~~~
        self.svd_groupbox = QGroupBox("ROI settings:")
        self.svd_groupbox.setStyleSheet(
            "QGroupBox { border: 1px solid white; border-style: outset; border-radius: 10px; color:white; padding: 20px 0px;}"
        )  # padding: 5px -10px;
        self.svd_groupbox.setLayout(QGridLayout())

        # Create ROI features
        self.comboBox = QComboBox(self)
        self.comboBox.addItem("Select ROI")
        self.comboBox.addItem("Pupil")
        self.comboBox.addItem("motion SVD")
        self.comboBox.addItem("Blink")
        self.comboBox.addItem("Running")
        self.comboBox.addItem("Face (pose)")
        self.newROI = 0
        self.comboBox.setCurrentIndex(0)
        self.svd_groupbox.layout().addWidget(self.comboBox, 0, 0)
        # self.comboBox.currentIndexChanged.connect(self.mode_change)
        self.addROI = QPushButton("Add ROI")
        self.addROI.setFont(QFont("Arial", 10, QFont.Bold))
        self.addROI.clicked.connect(lambda clicked: self.add_ROI())
        self.addROI.setEnabled(False)
        self.svd_groupbox.layout().addWidget(self.addROI, 0, 1)

        svdbin_label = QLabel("SVD spatial bin:")
        svdbin_label.setStyleSheet("color: gray;")
        self.svd_groupbox.layout().addWidget(svdbin_label, 1, 0)
        self.svdbin_spinbox = QSpinBox()
        self.svdbin_spinbox.setRange(1, 20)
        self.svdbin_spinbox.setValue(self.ops["sbin"])
        self.svd_groupbox.layout().addWidget(self.svdbin_spinbox, 1, 1)
        binLabel = QLabel("Pupil sigma:")
        binLabel.setStyleSheet("color: gray;")
        self.svd_groupbox.layout().addWidget(binLabel, 2, 0)
        self.sigma_box = QLineEdit()
        self.sigma_box.setText(str(self.ops["pupil_sigma"]))
        self.sigma_box.setFixedWidth(int(0.03 * self.sizeObject.width()))
        self.pupil_sigma = float(self.sigma_box.text())
        self.sigma_box.returnPressed.connect(self.pupil_sigma_change)
        self.svd_groupbox.layout().addWidget(self.sigma_box, 2, 1)

        # ~~~~~~~~~~~~~~~~~~~~~~~~ Pose/keypoints variables ~~~~~~~~~~~~~~~~~~~~~~~~
        self.pose_groupbox = QGroupBox("Pose settings:")
        self.pose_groupbox.setStyleSheet(
            "QGroupBox { border: 1px solid white; border-style: outset; border-radius: 10px; color:white; padding: 25px 5px;}"
        )
        self.pose_groupbox.setLayout(QGridLayout())

        self.is_pose_loaded = False
        keypoints_threshold_label = QLabel("Threshold:")
        keypoints_threshold_label.setStyleSheet("color: gray;")
        self.pose_groupbox.layout().addWidget(keypoints_threshold_label, 1, 0)
        self.keypoints_threshold_spinbox = QSpinBox()
        self.keypoints_threshold_spinbox.setRange(0, 100)
        self.keypoints_threshold_spinbox.setValue(0)
        self.keypoints_threshold = self.keypoints_threshold_spinbox.value()
        self.keypoints_threshold_spinbox.valueChanged.connect(
            self.update_keypoints_threshold
        )
        self.pose_groupbox.layout().addWidget(self.keypoints_threshold_spinbox, 1, 1)

        # ~~~~~~~~~~~~~~~~~~~~~~~~ Process features ~~~~~~~~~~~~~~~~~~~~~~~~
        self.process_groupbox = QGroupBox("Process settings:")
        self.process_groupbox.setStyleSheet(
            "QGroupBox { border: 1px solid white; border-style: outset; border-radius: 10px; color:white; padding: 25px 5px;}"
        )
        self.process_groupbox.setLayout(QGridLayout())

        # Check boxes
        self.motSVD_checkbox = QCheckBox("motSVD")
        self.motSVD_checkbox.setStyleSheet("color: gray;")
        self.process_groupbox.layout().addWidget(self.motSVD_checkbox, 0, 0)
        self.movSVD_checkbox = QCheckBox("movSVD")
        self.movSVD_checkbox.setStyleSheet("color: gray;")
        self.process_groupbox.layout().addWidget(self.movSVD_checkbox, 0, 1)
        self.keypoints_checkbox = QCheckBox("Keypoints")
        self.keypoints_checkbox.setStyleSheet("color: gray;")
        self.keypoints_checkbox.stateChanged.connect(self.update_pose)
        self.keypoints_checkbox.setEnabled(False)
        self.process_groupbox.layout().addWidget(self.keypoints_checkbox, 0, 2)

        self.save_mat = QCheckBox("Save *.mat")
        self.save_mat.setStyleSheet("color: gray;")
        if self.ops["save_mat"]:
            self.save_mat.toggle()
        self.process_groupbox.layout().addWidget(self.save_mat, 1, 0)
        self.multivideo_svd_checkbox = QCheckBox("multivideo")
        self.multivideo_svd_checkbox.setStyleSheet("color: gray;")
        if self.ops["fullSVD"]:
            self.multivideo_svd_checkbox.toggle()
        self.process_groupbox.layout().addWidget(self.multivideo_svd_checkbox, 1, 1)

        # ~~~~~~~~~~~~~~~~~~~~~~~~ Process buttons ~~~~~~~~~~~~~~~~~~~~~~~~
        self.process_buttons_groupbox = QGroupBox("Process buttons:")
        self.process_buttons_groupbox.setStyleSheet(
            "QGroupBox { border: 0px solid white; border-style: outset;}"
        )
        self.process_buttons_groupbox.setLayout(QGridLayout())

        self.saverois = QPushButton("save ROIs")
        self.saverois.setFont(QFont("Arial", 10, QFont.Bold))
        self.saverois.clicked.connect(self.save_ROIs)
        self.saverois.setEnabled(False)
        self.process_buttons_groupbox.layout().addWidget(self.saverois, 0, 0)

        self.process = QPushButton("process")
        self.process.setFont(QFont("Arial", 10, QFont.Bold))
        self.process.clicked.connect(self.process_ROIs)
        self.process.setEnabled(False)
        self.process_buttons_groupbox.layout().addWidget(self.process, 0, 1)

        self.processbatch = QPushButton("process batch \u2b07")
        self.processbatch.setFont(QFont("Arial", 10, QFont.Bold))
        self.processbatch.clicked.connect(self.process_batch)
        self.processbatch.setEnabled(False)
        self.process_buttons_groupbox.layout().addWidget(self.processbatch, 0, 2)

        # ~~~~~~~~~~~~~~~~~~~~~~~~ Labels ~~~~~~~~~~~~~~~~~~~~~~~~
        self.labels_groupbox = QGroupBox()
        self.labels_groupbox.setStyleSheet(
            "QGroupBox { border: 0px solid white; border-style: outset;}"
        )
        self.labels_groupbox.setLayout(QGridLayout())

        video_path_label = QLabel("Save path:")
        video_path_label.setStyleSheet("color: gray;")
        self.labels_groupbox.layout().addWidget(video_path_label, 0, 0)
        self.savelabel = QLabel("same as video")
        self.savelabel.setStyleSheet("color: white;")
        self.savelabel.setAlignment(QtCore.Qt.AlignCenter)
        self.labels_groupbox.layout().addWidget(self.savelabel, 0, 1)

        self.batchlist = []
        self.batchname = []
        for k in range(5):
            self.batchname.append(QLabel(""))
            self.batchname[-1].setStyleSheet("color: white;")
            self.batchname[-1].setAlignment(QtCore.Qt.AlignCenter)
            self.labels_groupbox.layout().addWidget(self.batchname[-1], k + 1, 0)
            # self.scene_grid_layout.addWidget(self.batchname[-1], 6 + k, 0, 1, 4)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Video playback options ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.current_frame_lineedit = QLineEdit()
        self.current_frame_lineedit.setMaxLength(10)
        self.current_frame_lineedit.setFixedSize(
            QtCore.QSize(
                np.floor(self.sizeObject.width() * 0.05).astype(int),
                np.floor(self.sizeObject.width() * 0.01).astype(int),
            )
        )
        self.current_frame_lineedit.textChanged[str].connect(self.set_frame_changed)
        self.total_frames_label = QLabel("0")
        self.total_frames_label.setStyleSheet("color: white;")
        self.frame_slider = QSlider(QtCore.Qt.Horizontal)
        self.frame_slider.setTickInterval(5)
        self.frame_slider.setTracking(False)
        self.frame_slider.valueChanged.connect(self.go_to_frame)
        self.frameDelta = 10
        istretch = 15
        iplay = istretch + 10
        iconSize = QtCore.QSize(20, 20)

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Video playback options ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.video_playback_groupbox = QGroupBox()
        self.video_playback_groupbox.setStyleSheet(
            "QGroupBox { border: 0px solid white; border-style: outset;}"
        )
        self.video_playback_groupbox.setLayout(QGridLayout())

        iconSize = QtCore.QSize(30, 30)
        self.playButton = QToolButton()
        self.playButton.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_MediaPlay)
        )
        self.playButton.setIconSize(iconSize)
        self.playButton.setToolTip("Play")
        self.playButton.setCheckable(True)
        self.playButton.clicked.connect(self.start)
        self.playButton.setFixedSize(
            QtCore.QSize(
                np.floor(self.sizeObject.width() * 0.025).astype(int),
                np.floor(self.sizeObject.width() * 0.025).astype(int),
            )
        )
        self.video_playback_groupbox.layout().addWidget(self.playButton, 0, 0)

        self.pauseButton = QToolButton()
        self.pauseButton.setCheckable(True)
        self.pauseButton.setIcon(
            self.style().standardIcon(QtWidgets.QStyle.SP_MediaPause)
        )
        self.pauseButton.setIconSize(iconSize)
        self.pauseButton.setToolTip("Pause")
        self.pauseButton.clicked.connect(self.pause)
        self.pauseButton.setFixedSize(
            QtCore.QSize(
                np.floor(self.sizeObject.width() * 0.025).astype(int),
                np.floor(self.sizeObject.width() * 0.025).astype(int),
            )
        )
        self.video_playback_groupbox.layout().addWidget(self.pauseButton, 0, 1)

        btns = QButtonGroup(self)
        btns.addButton(self.playButton, 0)
        btns.addButton(self.pauseButton, 1)
        btns.setExclusive(True)

        # Add clustering analysis/visualization features
        self.roi_embed_combobox = QComboBox(self)
        self.roi_embed_combobox.addItem("--Select display--")
        self.roi_embed_combobox.addItem("ROI")
        self.roi_embed_combobox.addItem("UMAP")
        self.roi_embed_combobox.addItem("tSNE")
        self.roi_embed_combobox.currentIndexChanged.connect(
            self.vis_combobox_selection_changed
        )
        self.roi_display_combobox = QComboBox(self)
        self.roi_display_combobox.hide()
        self.roi_display_combobox.activated.connect(self.display_ROI)
        self.run_clustering_button = QPushButton("Run")
        self.run_clustering_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.run_clustering_button.clicked.connect(
            lambda clicked: self.cluster_model.run(clicked, self)
        )
        self.run_clustering_button.hide()
        self.save_clustering_button = QPushButton("Save")
        self.save_clustering_button.setFont(QFont("Arial", 10, QFont.Bold))
        self.save_clustering_button.clicked.connect(
            lambda clicked: self.cluster_model.save_dialog(clicked, self)
        )
        self.save_clustering_button.hide()
        self.data_clustering_combobox = QComboBox(self)
        self.data_clustering_combobox.hide()
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setMaximumWidth(
            int(0.3 * self.data_clustering_combobox.width())
        )
        self.zoom_in_button.clicked.connect(
            lambda clicked: self.cluster_plot_zoom_buttons("in")
        )
        self.zoom_in_button.hide()
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setMaximumWidth(
            int(0.3 * self.data_clustering_combobox.width())
        )
        self.zoom_out_button.clicked.connect(
            lambda clicked: self.cluster_plot_zoom_buttons("out")
        )
        self.zoom_out_button.hide()

        # Add features to window
        # ~~~~~~~~~~ motsvd/movsvd options ~~~~~~~~~~
        self.scene_grid_layout.addWidget(facemap_label, 0, 0, 1, 2)
        self.scene_grid_layout.addWidget(self.svd_groupbox, 1, 0, 1, 2)
        # ~~~~~~~~~~ Pose features ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.pose_groupbox, 2, 0, 1, 2)
        # ~~~~~~~~~~ Process features ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.process_groupbox, 3, 0, 1, 2)
        # ~~~~~~~~~~ Process buttons features ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.process_buttons_groupbox, 4, 0, 1, 2)
        # ~~~~~~~~~~ Save/file IO ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.labels_groupbox, 5, 0, 1, 2)
        # ~~~~~~~~~~ Saturation ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.saturation_groupbox, 0, 3, 1, 2)
        # ~~~~~~~~~~ embedding & ROI visualization window features
        self.scene_grid_layout.addWidget(self.roi_saturation_groupbox, 8, 3, 1, 2)
        self.scene_grid_layout.addWidget(self.roi_embed_combobox, 8, 5, 1, 1)
        self.scene_grid_layout.addWidget(self.zoom_in_button, 8, 6, 1, 1)
        self.scene_grid_layout.addWidget(self.zoom_out_button, 8, 7, 1, 1)
        self.scene_grid_layout.addWidget(self.roi_display_combobox, 8, 6, 1, 1)
        self.scene_grid_layout.addWidget(self.save_clustering_button, 9, 6, 1, 1)
        #   ~~~~~~~~~~ Video playback ~~~~~~~~~~
        self.scene_grid_layout.addWidget(self.video_playback_groupbox, iplay, 0, 1, 1)
        self.playButton.setEnabled(False)
        self.pauseButton.setEnabled(False)
        self.pauseButton.setChecked(True)
        self.scene_grid_layout.addWidget(QLabel(""), istretch, 0, 1, 3)
        self.scene_grid_layout.setRowStretch(istretch, 1)
        self.scene_grid_layout.addWidget(
            self.current_frame_lineedit, istretch + 7, 0, 1, 1
        )
        self.scene_grid_layout.addWidget(self.total_frames_label, istretch + 7, 1, 1, 1)
        self.scene_grid_layout.addWidget(self.frame_slider, istretch + 10, 1, 1, 16)

        # Plot 1 and 2 features
        plot_label = QLabel("Keypoints traces")
        plot_label.setStyleSheet("color: gray;")
        self.scene_grid_layout.addWidget(plot_label, istretch, 0, 1, 1)
        plot_label = QLabel("SVD traces")
        plot_label.setStyleSheet("color: gray;")
        self.scene_grid_layout.addWidget(plot_label, istretch, 1, 1, 1)
        self.load_trace2_button = QPushButton("Load 1D data")
        self.load_trace2_button.setFont(QFont("Arial", 12))
        self.load_trace2_button.clicked.connect(
            lambda: self.load_1dtrace_button_clicked(2)
        )
        self.load_trace2_button.setEnabled(False)
        self.load_trace2_button.setFixedWidth(int(0.07 * self.sizeObject.width()))
        self.trace2_data_loaded = None
        self.trace2_legend = pg.LegendItem(labelTextSize="12pt", horSpacing=30)
        self.scene_grid_layout.addWidget(self.load_trace2_button, istretch + 1, 1, 1, 1)
        self.plot1_checkboxes = []
        self.plot2_checkboxes = []
        self.lbls = []
        # Set plot 1 checkboxes
        for i in range(len(self.keypoints_groups)):
            self.plot1_checkboxes.append(QCheckBox(self.keypoints_groups[i]))
            self.plot1_checkboxes[-1].setEnabled(False)
            self.plot1_checkboxes[-1].setStyleSheet("color: gray;")
            self.plot1_checkboxes[-1].toggled.connect(
                self.keypoint_subgroup_checkbox_toggled
            )
            self.scene_grid_layout.addWidget(
                self.plot1_checkboxes[-1], istretch + 1 + i, 0, 1, 1
            )
        # Set plot 2 checkboxes
        for k in range(4):
            self.plot2_checkboxes.append(QCheckBox(""))
            self.scene_grid_layout.addWidget(
                self.plot2_checkboxes[-1], istretch + 2 + k, 1, 1, 1
            )
            self.plot2_checkboxes[-1].toggled.connect(self.plot_processed)
            self.plot2_checkboxes[-1].setEnabled(False)
            self.plot2_checkboxes[k].setStyleSheet("color: gray;")
            self.lbls.append(QLabel(""))
            self.lbls[-1].setStyleSheet("color: white;")
        self.update_frame_slider()

    def set_saturation_label(self):
        self.saturation_level_label.setText(str(self.saturation_sliders[0].value()))

    def set_ROI_saturation_label(self, val=None):
        if val is None:
            self.roi_saturation_label.setText(str(self.saturation_sliders[1].value()))
        else:
            self.roi_saturation_label.setText(str(int(val)))

    def set_frame_changed(self, text):
        self.cframe = int(float(self.current_frame_lineedit.text()))
        self.jump_to_frame()
        if self.cluster_model.embedded_output is not None:
            self.highlight_embed_point(self.cframe)

    def reset(self):
        self.update_window_title()
        if len(self.rROI) > 0:
            for r in self.rROI:
                if len(r) > 0:
                    for rr in r:
                        rr.remove(self)
        if len(self.ROIs) > 0:
            for r in self.ROIs[::-1]:
                r.remove(self)
        self.ROIs = []
        self.rROI = []
        self.reflectors = []
        self.saturation = []
        self.iROI = 0
        self.nROIs = 0
        self.saturation = []
        self.clear_visualization_window()
        # Clear clusters
        self.cluster_model.disable_data_clustering_features(self)
        self.roi_embed_combobox.setCurrentIndex(0)
        self.clustering_plot.clear()
        self.clustering_plot_legend.clear()
        # Clear keypoints when a new file is loaded
        self.pose_scatterplot.clear()
        self.is_pose_loaded = False
        self.trace2_data_loaded = None
        self.traces2 = None
        # clear checkboxes
        for k in range(len(self.plot1_checkboxes)):
            self.plot1_checkboxes[k].setEnabled(False)
            self.plot1_checkboxes[k].setChecked(False)
        for k in range(len(self.plot2_checkboxes)):
            self.plot2_checkboxes[k].setText("")
            self.plot2_checkboxes[k].setEnabled(False)
            self.plot2_checkboxes[k].setChecked(False)
            self.lbls[k].setText("")
        # Clear pose variables
        self.pose_model = None
        self.poseFilepath = []
        self.keypoints_labels = []
        self.pose_x_coord = []
        self.pose_y_coord = []
        self.pose_likelihood = []
        self.keypoints_brushes = []
        self.bbox = []
        self.bbox_set = False
        # Update neural data variables
        self.neural_data_loaded = False
        self.neural_predictions_loaded = False
        # Clear plots
        self.keypoints_traces_plot.clear()
        self.svd_traces_plot.clear()
        self.neural_activity_plot.clear()
        self.neural_predictions_plot.clear()
        # Clear vticks
        self.keypoints_vtick = None
        self.svd_vtick = None
        self.neural_activity_vtick = None
        self.neural_predictions_vtick = None

    def pupil_sigma_change(self):
        self.pupil_sigma = float(self.sigma_box.text())
        if len(self.ROIs) > 0:
            self.ROIs[self.iROI].plot(self)

    def add_reflectROI(self):
        self.rROI[self.iROI].append(
            roi.reflectROI(
                iROI=self.iROI,
                wROI=len(self.rROI[self.iROI]),
                moveable=True,
                parent=self,
            )
        )

    def add_ROI(
        self,
        roitype=None,
        roistr=None,
        pos=None,
        ivid=None,
        xrange=None,
        yrange=None,
        moveable=True,
        resizable=True,
    ):
        if roitype is None and roistr is None:
            roitype = self.comboBox.currentIndex()
            roistr = self.comboBox.currentText()
        if "pose" in roistr:
            (
                self.bbox,
                self.bbox_set,
                self.resize_img,
                self.add_padding,
            ) = self.set_pose_bbox()
        elif roitype > 0:
            if self.online_mode and roitype > 1:
                self.invalid_roi_popup()
                return
            self.saturation.append(255.0)
            if len(self.ROIs) > 0:
                if self.ROIs[self.iROI].rind == 0:
                    for i in range(len(self.rROI[self.iROI])):
                        self.pROI.removeItem(self.rROI[self.iROI][i].ROI)
            self.iROI = self.nROIs
            self.ROIs.append(
                roi.sROI(
                    rind=roitype - 1,
                    rtype=roistr,
                    iROI=self.nROIs,
                    moveable=moveable,
                    resizable=resizable,
                    pos=pos,
                    parent=self,
                    ivid=ivid,
                    xrange=xrange,
                    yrange=yrange,
                    saturation=255,
                )
            )
            self.rROI.append([])
            self.reflectors.append([])
            self.nROIs += 1
            self.update_ROI_vis_comboBox()
            self.ROIs[-1].position(self)
        else:
            self.select_roi_popup()
            return

    def update_status_bar(self, message, update_progress=False, hide_progress=False):
        if update_progress:
            self.progressBar.show()
            progressBar_value = [
                int(s) for s in message.split("%")[0].split() if s.isdigit()
            ]
            if len(progressBar_value) > 0:
                self.progressBar.setValue(progressBar_value[0])
                total_frames = self.total_frames_label.text().split()[1]
                frames_processed = np.floor(
                    (progressBar_value[0] / 100) * float(total_frames)
                )
                self.current_frame_lineedit.setText(str(frames_processed))
                self.statusBar.showMessage(message.split("|")[0])
            else:
                self.statusBar.showMessage("Done!")
        else:
            if hide_progress:
                self.progressBar.hide()
            self.statusBar.showMessage(message)

    def keyPressEvent(self, event):
        bid = -1
        if self.playButton.isEnabled():
            if event.modifiers() != QtCore.Qt.ShiftModifier:
                if event.key() == QtCore.Qt.Key_Left:
                    self.cframe -= self.frameDelta
                    self.cframe = np.maximum(
                        0, np.minimum(self.nframes - 1, self.cframe)
                    )
                    self.frame_slider.setValue(self.cframe)
                elif event.key() == QtCore.Qt.Key_Right:
                    self.cframe += self.frameDelta
                    self.cframe = np.maximum(
                        0, np.minimum(self.nframes - 1, self.cframe)
                    )
                    self.frame_slider.setValue(self.cframe)
        if event.modifiers() != QtCore.Qt.ShiftModifier:
            if event.key() == QtCore.Qt.Key_Space:
                if self.playButton.isEnabled():
                    # then play
                    self.start()
                else:
                    self.pause()

    def go_to_frame(self):
        self.cframe = int(self.frame_slider.value())
        self.current_frame_lineedit.setText(str(self.cframe))

    def fitToWindow(self):
        self.movieLabel.setScaledContents(self.fitCheckBox.isChecked())

    def update_frame_slider(self):
        self.frame_slider.setMaximum(self.nframes - 1)
        self.frame_slider.setMinimum(0)
        self.frame_slider.setEnabled(True)

    def jump_to_frame(self):
        if self.playButton.isEnabled():
            self.cframe = np.maximum(0, np.minimum(self.nframes - 1, self.cframe))
            self.cframe = int(self.cframe)
            self.cframe -= 1
            self.img = utils.get_frame(
                self.cframe, self.nframes, self.cumframes, self.video
            )
            for i in range(len(self.img)):
                self.imgs[i][:, :, :, 1] = self.img[i].copy()
            img = utils.get_frame(
                self.cframe + 1, self.nframes, self.cumframes, self.video
            )
            for i in range(len(self.img)):
                self.imgs[i][:, :, :, 2] = img[i]
            self.next_frame()

    def next_frame(self):
        if not self.online_mode:
            # loop after video finishes
            """
            if self.neural_data_loaded:
                idx = bisect_left(self.neural_activity_data.behavior_timestamps_resampled, self.cframe)
                self.cframe = self.neural_activity_data.behavior_timestamps_resampled[idx + 1]
            else:
                self.cframe += 1
            """
            self.cframe += 1
            if self.cframe > self.nframes - 1:
                self.cframe = 0
            for i in range(len(self.imgs)):
                self.imgs[i][:, :, :, :2] = self.imgs[i][:, :, :, 1:]
            im = utils.get_frame(
                self.cframe + 1, self.nframes, self.cumframes, self.video
            )
            for i in range(len(self.imgs)):
                self.imgs[i][:, :, :, 2] = im[i]
                self.img[i] = self.imgs[i][:, :, :, 1].copy()
                self.fullimg[
                    self.sy[i] : self.sy[i] + self.Ly[i],
                    self.sx[i] : self.sx[i] + self.Lx[i],
                ] = self.img[i]
            self.frame_slider.setValue(self.cframe)
        else:
            self.online_plotted = False
            # online.get_frame(self)

        if len(self.ROIs) > 0 and self.roi_embed_combobox.currentText() == "ROI":
            self.ROIs[self.iROI].plot(self)

        self.pimg.setImage(self.fullimg)
        self.pimg.setLevels([0, self.sat[0]])
        self.current_frame_lineedit.setText(str(self.cframe))
        self.update_pose()
        if self.neural_data_loaded:
            self.update_neural_data_vtick()
        if self.neural_predictions_loaded:
            self.update_neural_predictions_vtick()
        if self.is_pose_loaded:
            self.update_keypoints_vtick()
        if self.processed or self.trace2_data_loaded is not None:
            self.update_svd_vtick()
        self.total_frames_label.setText("/ " + str(self.nframes) + " frames")
        self.video_window.show()
        self.show()

    def start(self):
        if self.online_mode:
            self.online_traces = None
            self.keypoints_traces_plot.show()
            self.playButton.setEnabled(False)
            self.pauseButton.setEnabled(True)
            self.frame_slider.setEnabled(False)
            self.updateTimer.start(50)  # 25
        elif self.cframe < self.nframes - 1:
            self.playButton.setEnabled(False)
            self.pauseButton.setEnabled(True)
            self.frame_slider.setEnabled(False)
            self.updateTimer.start(50)  # 25
        self.update_pose()

    def pause(self):
        self.updateTimer.stop()
        self.playButton.setEnabled(True)
        self.pauseButton.setEnabled(False)
        self.frame_slider.setEnabled(True)
        if self.online_mode:
            self.online_traces = None
        self.update_pose()

    def save_ops(self):
        ops = {
            "sbin": self.sbin,
            "pupil_sigma": float(self.sigma_box.text()),
            "save_path": self.save_path,
            "fullSVD": self.multivideo_svd_checkbox.isChecked(),
            "save_mat": self.save_mat.isChecked(),
        }
        opsfile = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "ops_user.npy"
        )
        np.save(opsfile, ops)
        return ops

    def update_buttons(self):
        self.playButton.setEnabled(True)
        self.pauseButton.setEnabled(False)
        self.addROI.setEnabled(True)
        self.pauseButton.setChecked(True)
        self.process.setEnabled(True)
        self.saverois.setEnabled(True)
        self.multivideo_svd_checkbox.setChecked(True)
        self.save_mat.setChecked(True)
        self.load_trace2_button.setEnabled(True)

        # Enable pose features for single video only
        self.keypoints_checkbox.setEnabled(True)

    def button_status(self, status):
        self.playButton.setEnabled(status)
        self.pauseButton.setEnabled(status)
        self.frame_slider.setEnabled(status)
        self.process.setEnabled(status)
        self.saverois.setEnabled(status)

    ### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  Process options ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def save_ROIs(self):
        self.sbin = int(self.svdbin_spinbox.value())
        # save running parameters as defaults
        ops = self.save_ops()
        if len(self.save_path) > 0:
            savepath = self.save_path
        else:
            savepath = None
        if len(self.ROIs) > 0:
            rois = utils.roi_to_dict(self.ROIs, self.rROI)
        else:
            rois = None
        pose_settings = {
            "bbox": self.bbox,
            "bbox_set": self.bbox_set,
            "resize_img": self.resize_img,
            "add_padding": self.add_padding,
        }
        proc = {
            "Ly": self.Ly,
            "Lx": self.Lx,
            "sy": self.sy,
            "sx": self.sx,
            "LY": self.LY,
            "LX": self.LX,
            "sbin": ops["sbin"],
            "fullSVD": ops["fullSVD"],
            "rois": rois,
            "motSVD": self.motSVD_checkbox.isChecked(),
            "movSVD": self.movSVD_checkbox.isChecked(),
            "pose_settings": pose_settings,
            "save_mat": ops["save_mat"],
            "save_path": ops["save_path"],
            "filenames": self.filenames,
        }
        savename = process.save(proc, savepath=savepath)
        self.update_status_bar("ROIs saved in " + savepath)
        self.batchlist.append(savename)
        _, filename = os.path.split(savename)
        filename, _ = os.path.splitext(filename)
        self.batchname[len(self.batchlist) - 1].setText(filename)
        self.processbatch.setEnabled(True)

    def process_batch(self):
        files = self.batchlist
        for f in files:
            proc = np.load(f, allow_pickle=True).item()
            if proc["motSVD"] or proc["movSVD"]:
                savename = process.run(
                    proc["filenames"],
                    motSVD=proc["motSVD"],
                    movSVD=proc["movSVD"],
                    GUIobject=QtWidgets,
                    proc=proc,
                    savepath=proc["save_path"],
                )
                self.update_status_bar("Processed " + savename)

            pose.Pose(
                gui=None,
                filenames=proc["filenames"],
                bbox=proc["pose_settings"]["bbox"],
                bbox_set=proc["pose_settings"]["bbox_set"],
                resize=proc["pose_settings"]["resize_img"],
                add_padding=proc["pose_settings"]["add_padding"],
            ).run(plot=False)
        if len(files) == 1 and (proc["motSVD"] or proc["movSVD"]):
            io.open_proc(self, file_name=savename)

    def process_ROIs(self):
        self.sbin = int(self.svdbin_spinbox.value())
        # save running parameters as defaults
        ops = self.save_ops()
        if len(self.save_path) > 0:
            savepath = self.save_path
        else:
            savepath = None
        if self.motSVD_checkbox.isChecked() or self.movSVD_checkbox.isChecked():
            savename = process.run(
                self.filenames, GUIobject=QtWidgets, parent=self, savepath=savepath
            )
            io.open_proc(self, file_name=savename)
            print("Output saved in", savepath)
            self.update_status_bar("Output saved in " + savepath)
        if self.keypoints_checkbox.isChecked():
            self.setup_pose_model()
            if not self.pose_gui.cancel_bbox_selection:
                self.pose_model.run_all()
                self.update_status_bar("Pose labels saved in " + savepath)
            else:
                self.update_status_bar("Pose estimation cancelled")

    def process_subset_keypoints(self, subset_frame_indices):
        if self.pose_model is None:
            self.setup_pose_model()
        if not self.pose_gui.cancel_bbox_selection:
            if subset_frame_indices is not None:
                pred_data, subset_ind, bbox = self.pose_model.run_subset(
                    subset_frame_indices
                )
            else:
                pred_data, subset_ind, bbox = self.pose_model.run_subset()
            self.update_status_bar("Subset keypoints processed")
            return pred_data.cpu().numpy(), subset_ind, bbox
        else:
            self.update_status_bar("Training cancelled")
            return None

    ### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Pose functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def train_model(
        self,
        image_data,
        keypoints_data,
        num_epochs,
        batch_size,
        learning_rate,
        weight_decay,
    ):
        if self.pose_model is None:
            self.setup_pose_model()
        if not self.pose_gui.cancel_bbox_selection:
            self.pose_model.train(
                image_data,
                keypoints_data,
                num_epochs,
                batch_size,
                learning_rate,
                weight_decay,
            )
            self.update_status_bar("Model training completed!")
        return

    def set_pose_bbox(self):
        # User defined bbox selection
        self.pose_gui = pose_gui.PoseGUI(gui=self)
        (
            self.bbox,
            self.bbox_set,
            self.resize_img,
            self.add_padding,
        ) = self.pose_gui.draw_user_bbox()
        return self.bbox, self.bbox_set, self.resize_img, self.add_padding

    def setup_pose_model(self):
        if not self.bbox_set:
            (
                self.bbox,
                self.bbox_set,
                self.resize_img,
                self.add_padding,
            ) = self.set_pose_bbox()
        if self.pose_model is None and not self.pose_gui.cancel_bbox_selection:
            self.pose_model = pose.Pose(
                gui=self,
                GUIobject=QtWidgets,
                filenames=self.filenames,
                bbox=self.bbox,
                bbox_set=self.bbox_set,
                resize=self.resize_img,
                add_padding=self.add_padding,
            )
            self.pose_model.pose_prediction_setup()

    def visualize_subset_keypoints(self, video_id, pred_data, subset_ind, bodyparts):
        pose_gui.VisualizeVideoSubset(self, video_id, pred_data, subset_ind, bodyparts)

    def show_model_training_popup(self):
        if self.process.isEnabled():
            refine_pose.ModelTrainingPopup(gui=self)
        else:
            self.load_video_popup()

    def save_pose_model(self, output_folder_path):
        """
        Save pose model to folder path specified by user
        """
        if self.pose_model is None:
            self.setup_pose_model()
        savepath = self.pose_model.save_model(output_folder_path)
        self.update_status_bar("Model saved to {}".format(savepath), hide_progress=True)
        print("Model saved to {}".format(savepath))

    def load_finetuned_model(self):
        if not self.process.isEnabled():
            self.load_video_popup()
        model_path = io.get_pose_model_filepath(self)
        if model_path is None:
            return
        if self.pose_model is None:
            self.setup_pose_model()
        self.pose_model.load_model(model_path)
        self.update_status_bar("Model loaded from:", model_path, hide_progress=True)
        self.model_loaded_popup(model_path)

    def update_keypoints_threshold(self, value):
        if self.is_pose_loaded:
            self.keypoints_threshold = np.nanpercentile(
                self.pose_likelihood, value
            )  # TODO - use threshold to update keypoints traces as well

    def load_keypoints(self):
        # Read Pose file
        self.keypoints_labels = []
        self.pose_x_coord = []
        self.pose_y_coord = []
        self.pose_likelihood = []
        for video_id in range(len(self.poseFilepath)):
            print("Loading keypoints:", self.poseFilepath[video_id])
            pose_data = pd.read_hdf(self.poseFilepath[video_id], "df_with_missing")
            # Append pose data to list for each video_id
            self.keypoints_labels.append(
                pd.unique(pose_data.columns.get_level_values("bodyparts"))
            )
            self.pose_x_coord.append(
                pose_data.T[
                    pose_data.columns.get_level_values("coords").values == "x"
                ].values
            )  # size: key points x frames
            self.pose_y_coord.append(
                pose_data.T[
                    pose_data.columns.get_level_values("coords").values == "y"
                ].values
            )  # size: key points x frames
            self.pose_likelihood.append(
                pose_data.T[
                    pose_data.columns.get_level_values("coords").values == "likelihood"
                ].values
            )  # size: key points x frames
            # Choose colors for each label: provide option for paltter that is color-blindness friendly
            colors = cm.get_cmap("jet")(
                np.linspace(0, 1.0, len(self.keypoints_labels[video_id]))
            )
            colors *= 255
            colors = colors.astype(int)
            self.keypoints_brushes.append(
                np.array([pg.mkBrush(color=c) for c in colors])
            )
            self.is_pose_loaded = True
            self.keypoints_checkbox.setChecked(True)
            self.plot_trace(
                wplot=1,
                proctype=5,
                wroi=None,
                color=None,
                keypoints_group_selected=["Eye"],
            )
        for k in range(len(self.plot1_checkboxes)):
            self.plot1_checkboxes[k].setEnabled(True)
        self.plot1_checkboxes[0].setChecked(True)
        self.update_pose()
        self.update_status_bar("Keypoints loaded", hide_progress=True)

    def update_pose(self):
        if self.is_pose_loaded and self.keypoints_checkbox.isChecked():
            self.statusBar.clearMessage()
            self.p0.addItem(self.pose_scatterplot)
            self.p0.setRange(xRange=(0, self.LX), yRange=(0, self.LY), padding=0.0)
            x, y, labels, brushes = (
                np.array([]),
                np.array([]),
                np.array([]),
                np.array([]),
            )
            for video_id in range(len(self.poseFilepath)):
                filtered_keypoints = np.where(
                    self.pose_likelihood[video_id][:, self.cframe]
                    > self.keypoints_threshold
                )[0]
                x_coord = (
                    self.pose_x_coord[video_id] + self.sx[video_id]
                )  # shift x coordinates
                x = np.append(x, x_coord[filtered_keypoints, self.cframe])
                y_coord = (
                    self.pose_y_coord[video_id] + self.sy[video_id]
                )  # shift y coordinates
                y = np.append(y, y_coord[filtered_keypoints, self.cframe])
                labels = np.append(
                    labels, self.keypoints_labels[video_id][filtered_keypoints]
                )
                brushes = np.append(
                    brushes, self.keypoints_brushes[video_id][filtered_keypoints]
                )
            self.pose_scatterplot.setData(
                x,
                y,
                size=0.009 * self.sizeObject.height(),
                symbol="o",
                brush=brushes,
                hoverable=True,
                hoverSize=10,
                data=labels,
            )
        elif not self.is_pose_loaded and self.keypoints_checkbox.isChecked():
            self.update_status_bar("Please upload a pose (*.h5) file")
        else:
            self.statusBar.clearMessage()
            self.pose_scatterplot.clear()

    def keypoints_clicked(self, obj, points):
        # Show trace of keypoint clicked
        # Get name of keypoint clicked and its index
        if (
            self.is_pose_loaded
            and self.keypoints_checkbox.isChecked()
            and len(points) > 0
        ):
            keypoint_name = points[0].data()
            # Get name of subgroup of keypoint clicked
            for idx, subgroup in enumerate(self.keypoints_subgroups):
                if keypoint_name in subgroup:
                    keypoint_group_index = idx
                    break
            # Plot trace of keypoint clicked
            self.plot_trace(
                wplot=1,
                proctype=5,
                wroi=None,
                color=None,
                keypoints_group_selected=[self.keypoints_groups[keypoint_group_index]],
            )

    def keypoint_subgroup_checkbox_toggled(self, obj):
        if self.is_pose_loaded and self.keypoints_checkbox.isChecked():
            # Get names of plot 1 checkboxes that are checked
            checked_checkboxes = [
                self.plot1_checkboxes[i].text()
                for i in range(len(self.plot1_checkboxes))
                if self.plot1_checkboxes[i].isChecked()
            ]
            if len(checked_checkboxes) > 0:
                # Plot traces of keypoints that are checked
                self.plot_trace(
                    wplot=1,
                    proctype=5,
                    wroi=None,
                    color=None,
                    keypoints_group_selected=checked_checkboxes,
                )
            else:
                self.keypoints_traces_plot.clear()

    def keypoints_hovered(self, obj, ev):
        point_hovered = np.where(self.pose_scatterplot.data["hovered"])[0]
        if (
            point_hovered.shape[0] >= 1
        ):  # Show tooltip only when hovering over a point i.e. no empty array
            points = self.pose_scatterplot.points()
            vb = self.pose_scatterplot.getViewBox()
            if vb is not None and self.pose_scatterplot.opts["tip"] is not None:
                cutoff = 1  # Display info of only one point when hovering over multiple points
                tip = [
                    self.pose_scatterplot.opts["tip"](
                        data=points[pt].data(),
                        x=points[pt].pos().x(),
                        y=points[pt].pos().y(),
                    )
                    for pt in point_hovered[:cutoff]
                ]
                if len(point_hovered) > cutoff:
                    tip.append("({} other...)".format(len(point_hovered) - cutoff))
                vb.setToolTip("\n\n".join(tip))

    ### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Plot 1 and 2 functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def load_1dtrace_button_clicked(self, plot_id):
        try:
            data = io.load_trace_data(parent=self)
            if data.ndim != 1:
                self.invalid_trace_popup()
                return
            # Open a QDialog box containing two radio buttons horizontally centered
            # and a QLineEdit to enter the name of the trace
            # If the user presses OK, the trace is added to the list of traces
            # and the combo box is updated
            # If the user presses Cancel, the trace is not added
            dialog = QtWidgets.QDialog()
            dialog.setWindowTitle("Set data type")
            dialog.setMinimumSize(
                np.floor(self.sizeObject.width() * 0.25).astype(int),
                np.floor(self.sizeObject.height() * 0.2).astype(int),
            )
            dialog.verticalLayout = QtWidgets.QVBoxLayout(dialog)
            dialog.verticalLayout.setContentsMargins(10, 10, 10, 10)

            dialog.horizontalLayout = QtWidgets.QHBoxLayout()
            dialog.verticalLayout.addLayout(dialog.horizontalLayout)
            dialog.label = QtWidgets.QLabel("Data type:")
            dialog.horizontalLayout.addWidget(dialog.label)

            # Create radio buttons
            dialog.radio_button_group = QtWidgets.QButtonGroup()
            dialog.radio_button_group.setExclusive(True)
            dialog.radioButton1 = QtWidgets.QRadioButton("Continuous")
            dialog.radioButton1.setChecked(True)
            dialog.horizontalLayout.addWidget(dialog.radioButton1)
            dialog.radioButton2 = QtWidgets.QRadioButton("Discrete")
            dialog.radioButton2.setChecked(False)
            dialog.horizontalLayout.addWidget(dialog.radioButton2)
            # Add radio buttons to radio buttons group
            dialog.radio_button_group.addButton(dialog.radioButton1)
            dialog.radio_button_group.addButton(dialog.radioButton2)

            dialog.horizontalLayout2 = QtWidgets.QHBoxLayout()
            dialog.label = QtWidgets.QLabel("Data name:")
            dialog.horizontalLayout2.addWidget(dialog.label)
            dialog.lineEdit = QtWidgets.QLineEdit()
            dialog.lineEdit.setText("Trace 1")
            # Adjust size of line edit
            dialog.lineEdit.setFixedWidth(200)
            dialog.horizontalLayout2.addWidget(dialog.lineEdit)
            dialog.verticalLayout.addLayout(dialog.horizontalLayout2)
            dialog.horizontalLayout3 = QtWidgets.QHBoxLayout()
            dialog.buttonBox = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            )
            dialog.buttonBox.accepted.connect(dialog.accept)
            dialog.buttonBox.rejected.connect(dialog.reject)
            dialog.horizontalLayout3.addWidget(dialog.buttonBox)
            dialog.verticalLayout.addLayout(dialog.horizontalLayout3)
            if not dialog.exec_():
                return
            # If the user presses OK, the trace is added to the list of traces
            data_name = dialog.lineEdit.text()
            if data_name == "":
                data_name = "trace"
            data_type = "continuous"
            if dialog.radioButton2.isChecked():
                data_type = "discrete"
                # Create a color palette of len(data) using distinguishable_colors
                # and add it to the list of color palettes
                # The color palette is used to color the points in the scatter
                if len(np.unique(data)) <= 10:
                    color_palette = np.array(plt.get_cmap("tab10").colors)
                elif len(np.unique(data)) <= 20:
                    color_palette = np.array(plt.get_cmap("tab20").colors)
                else:
                    num_classes = len(np.unique(data))
                    color_palette = cm.get_cmap("gist_rainbow")(
                        np.linspace(0, 1.0, num_classes)
                    )
                color_palette *= 255
                color_palette = color_palette.astype(int)
                # color_palette = color_palette[:len(np.unique(data))]
                # Create a list of pens for each unique value in data
                # The pen is used to color the points in the scatter plot
                pen_list = np.empty(len(data), dtype=object)
                for j, value in enumerate(np.unique(data)):
                    ind = np.where(data == value)[0]
                    pen_list[ind] = pg.mkPen(color_palette[j])
                vtick = QPainterPath()
                vtick.moveTo(0, -1)
                vtick.lineTo(0, 1)

            if plot_id == 2:
                self.trace2_data_loaded = data
                self.trace2_data_type = data_type
                self.trace2_name = data_name
                if data_type == "discrete":
                    x = np.arange(len(data))
                    y = np.ones((len(x)))
                    self.trace2_plot = pg.ScatterPlotItem()
                    self.trace2_plot.setData(
                        x,
                        y,
                        pen=pen_list,
                        brush="g",
                        pxMode=False,
                        symbol=vtick,
                        size=1,
                        symbol_pen=pen_list,
                    )
                else:
                    self.trace2_plot = pg.PlotDataItem()
                    self.trace2_plot.setData(data, pen=pg.mkPen("g", width=1))
                self.trace2_legend.clear()
                self.trace2_legend.addItem(self.trace2_plot, name=data_name)
                self.trace2_legend.setPos(self.trace2_plot.x(), self.trace2_plot.y())
                self.trace2_legend.setParentItem(self.svd_traces_plot)
                self.trace2_legend.setVisible(True)
                self.trace2_plot.setVisible(True)
                if self.svd_plot_vtick is None:
                    self.svd_plot_vtick = pg.InfiniteLine(
                        pos=self.cframe,
                        angle=90,
                        pen=pg.mkPen(color=(255, 255, 255), width=2, movable=True),
                    )
                    self.svd_traces_plot.addItem(self.svd_plot_vtick)
                self.update_status_bar("Trace 2 data updated")
                try:
                    self.trace2_legend.sigClicked.connect(self.mouseClickEvent)
                except Exception as e:
                    pass
            else:
                self.update_status_bar("Error: plot ID not recognized")
                pass
            self.plot_processed()
        except Exception as e:
            print(e)
            self.update_status_bar("Error: data not recognized")

    # Plot trace on keypoints_traces_plot showing cluster labels as discrete data
    def plot_cluster_labels(self, labels, color_palette):
        x = np.arange(len(labels))
        y = np.ones((len(x)))
        self.trace2_data_loaded = y
        self.trace2_data_type = "discrete"
        self.trace2_name = "Cluster Labels"
        # Create a list of pens for each unique value in data
        # The pen is used to color the points in the scatter plot
        pen_list = np.empty(len(labels), dtype=object)
        for j, value in enumerate(np.unique(labels)):
            ind = np.where(labels == value)[0]
            pen_list[ind] = pg.mkPen(color_palette[j])
        vtick = QPainterPath()
        vtick.moveTo(0, -1)
        vtick.lineTo(0, 1)
        # Plot trace 1 data points
        self.trace2_plot = pg.ScatterPlotItem()
        self.trace2_plot.setData(
            x,
            y,
            pen=pen_list,
            brush="g",
            pxMode=False,
            symbol=vtick,
            size=1,
            symbol_pen=pen_list,
        )
        self.trace2_legend.clear()
        self.trace2_legend.addItem(self.trace2_plot, name=self.trace2_name)
        self.trace2_legend.setPos(self.trace2_plot.x(), self.trace2_plot.y())
        self.trace2_legend.setParentItem(self.svd_traces_plot)
        self.trace2_legend.setVisible(True)
        self.trace2_plot.setVisible(True)
        self.update_status_bar("Trace 2 data updated")
        try:
            self.trace2_legend.sigClicked.connect(self.mouseClickEvent)
        except Exception as e:
            pass
        self.plot_processed()

    def plot_processed(self):
        self.svd_traces_plot.clear()
        if self.traces2 is None:
            self.traces2 = np.zeros((0, self.nframes))
        for k in range(len(self.plot2_checkboxes)):
            if self.plot2_checkboxes[k].isChecked():
                self.plot2_checkboxes[k].setText(self.lbls[k].text())
                self.plot2_checkboxes[k].setStyleSheet(self.lbls[k].styleSheet())
                tr = self.plot_trace(2, self.proctype[k], self.wroi[k], self.col[k])
                if tr.ndim < 2:
                    self.traces2 = np.concatenate(
                        (self.traces2, tr[np.newaxis, :]), axis=0
                    )
                else:
                    self.traces2 = np.concatenate((self.traces2, tr), axis=0)
            else:
                self.plot2_checkboxes[k].setText(self.lbls[k].text())
                self.plot2_checkboxes[k].setStyleSheet("color: gray")
        if self.trace2_data_loaded is not None:
            self.svd_traces_plot.addItem(self.trace2_plot)
            self.traces2 = np.concatenate(
                (self.traces2, self.trace2_data_loaded[np.newaxis, :]), axis=0
            )
            self.svd_traces_plot.setRange(
                xRange=(0, self.nframes), yRange=(-4, 4), padding=0.0
            )
        if self.svd_plot_vtick is None:
            self.svd_plot_vtick = pg.InfiniteLine(
                pos=self.cframe,
                angle=90,
                pen=pg.mkPen(color=(255, 255, 255), width=2, movable=True),
            )
            self.svd_traces_plot.addItem(self.svd_plot_vtick)
            print("Added vtick")
        self.svd_traces_plot.setRange(xRange=(0, self.nframes))
        self.svd_traces_plot.setLimits(xMin=0, xMax=self.nframes)
        self.svd_traces_plot.show()
        self.jump_to_frame()

    def plot_trace(self, wplot, proctype, wroi, color, keypoints_group_selected=None):
        if wplot == 1:
            selected_plot = self.keypoints_traces_plot
        elif wplot == 2:
            selected_plot = self.svd_traces_plot
        else:
            print("Invalid plot window")
            return
        if proctype == 0 or proctype == 2:  # motsvd
            if proctype == 0:
                ir = 0
            else:
                ir = wroi + 1
            cmap = cm.get_cmap("hsv")
            nc = min(10, self.motSVDs[ir].shape[1])
            cmap = (255 * cmap(np.linspace(0, 0.2, nc))).astype(int)
            norm = (self.motSVDs[ir][:, 0]).std()
            tr = (self.motSVDs[ir][:, :10] ** 2).sum(axis=1) ** 0.5 / norm
            for c in np.arange(0, nc, 1, int)[::-1]:
                pen = pg.mkPen(
                    tuple(cmap[c, :]), width=1
                )  # , style=QtCore.Qt.DashLine)
                tr2 = self.motSVDs[ir][:, c] / norm
                tr2 *= np.sign(skew(tr2))
                selected_plot.plot(tr2, pen=pen)
            pen = pg.mkPen(color)
            selected_plot.plot(tr, pen=pen)
            selected_plot.setRange(yRange=(-3, 3))
            if self.svd_plot_vtick is None:
                self.svd_plot_vtick = pg.InfiniteLine(
                    pos=self.cframe,
                    angle=90,
                    pen=pg.mkPen(color=(255, 255, 255), width=2, movable=True),
                )
                selected_plot.addItem(self.svd_plot_vtick)
                print("selected plot: ", selected_plot)
                print("self.svd_plot_vtick", self.svd_plot_vtick)
        elif proctype == 1:  # Pupil
            pup = self.pupil[wroi]
            pen = pg.mkPen(color, width=2)
            pp = selected_plot.plot(zscore(pup["area_smooth"]) * 2, pen=pen)
            if "com_smooth" in pup:
                pupcom = pup["com_smooth"].copy()
            else:
                pupcom = pup["com"].copy()
            pupcom -= pupcom.mean(axis=0)
            norm = pupcom.std()
            pen = pg.mkPen((155, 255, 155), width=1, style=QtCore.Qt.DashLine)
            py = selected_plot.plot(pupcom[:, 0] / norm * 2, pen=pen)
            pen = pg.mkPen((0, 100, 0), width=1, style=QtCore.Qt.DashLine)
            px = selected_plot.plot(pupcom[:, 1] / norm * 2, pen=pen)
            tr = np.concatenate(
                (
                    zscore(pup["area_smooth"])[np.newaxis, :] * 2,
                    pupcom[:, 0][np.newaxis, :] / norm * 2,
                    pupcom[:, 1][np.newaxis, :] / norm * 2,
                ),
                axis=0,
            )
            lg = selected_plot.addLegend(offset=(0, 0))
            lg.addItem(pp, "<font color='white'><b>area</b></font>")
            lg.addItem(py, "<font color='white'><b>ypos</b></font>")
            lg.addItem(px, "<font color='white'><b>xpos</b></font>")
        elif proctype == 3:  # Blink
            tr = zscore(self.blink[wroi])
            pen = pg.mkPen(color, width=2)
            selected_plot.plot(tr, pen=pen)
        elif proctype == 4:  # Running
            running = self.running[wroi]
            running *= np.sign(running.mean(axis=0))
            running -= running.min()
            running /= running.max()
            running *= 16
            running -= 8
            selected_plot.plot(running[:, 0], pen=color)
            selected_plot.plot(running[:, 1], pen=color)
            tr = running.T
        elif proctype == 5 and keypoints_group_selected is not None:  # Keypoints traces
            selected_plot.clear()
            # Get index of keypoints selected
            kp_selected_idx = []
            for i, keypoint_group in enumerate(keypoints_group_selected):
                # Get index of keypoint group selected
                keypoint_group_idx = self.keypoints_groups.index(keypoint_group)
                # Get keypoints of keypoint group selected
                keypoints = self.keypoints_subgroups[keypoint_group_idx]
                for _, bp in enumerate(keypoints):
                    kp_selected_idx.append(self.keypoints_labels[0].tolist().index(bp))
            kp_selected_idx = np.array(sorted(kp_selected_idx))
            # x-coordinates
            x_trace = self.pose_x_coord[0][kp_selected_idx]
            for i in range(x_trace.shape[0]):
                x_pen = pg.mkPen(
                    self.keypoints_brushes[0][kp_selected_idx[i]].color(), width=1
                )
                x_plot = selected_plot.plot(x_trace[i], pen=x_pen)
            lg = selected_plot.addLegend(colCount=2, offset=(0, 0))
            lg.addItem(
                x_plot,
                name="<font color='white'><b>{} x-coord</b></font>".format(
                    keypoints_group_selected
                ),
            )
            # y-coordinates
            y_trace = self.pose_y_coord[0][kp_selected_idx]
            for i in range(y_trace.shape[0]):
                y_pen = pg.mkPen(
                    self.keypoints_brushes[0][kp_selected_idx[i]].color(),
                    width=1,
                    style=QtCore.Qt.DashLine,
                )
                y_plot = selected_plot.plot(y_trace[i], pen=y_pen)
            lg.addItem(
                y_plot,
                name="<font color='white'><b>{} y-coord</b></font>".format(
                    keypoints_group_selected
                ),
            )
            # Position legend at the top right corner
            lg.setPos(selected_plot.x(), selected_plot.y())
            selected_plot.setRange(xRange=(0, x_trace.shape[1]))
            tr = None
            self.keypoints_vtick = pg.InfiniteLine(
                pos=self.cframe,
                angle=90,
                pen=pg.mkPen(color=(255, 255, 255), width=2, movable=True),
            )
            selected_plot.addItem(self.keypoints_vtick)
        selected_plot.setLimits(xMin=0, xMax=self.nframes)
        return tr

    def on_click_svd_plot(self, event):
        """
        Update vtick position of svd plot when user clicks
        """
        if event.button() == QtCore.Qt.LeftButton:
            mouse_point = self.svd_traces_plot.vb.mapSceneToView(event._scenePos)
            self.update_svd_vtick(mouse_point.x())

    def update_svd_vtick(self, x_pos=None):
        """
        Update vtick position of svd plot
        """
        if not self.processed:
            return
        if x_pos is not None:
            self.svd_plot_vtick.setPos(x_pos)
            frame = int(x_pos)
        else:
            self.svd_plot_vtick.setPos(self.cframe)
            frame = self.cframe
        # Check if x position is within the plot's current range of view
        if (
            not self.svd_traces_plot.getViewBox().viewRange()[0][0]
            <= frame
            <= self.svd_traces_plot.getViewBox().viewRange()[0][1]
        ):
            self.svd_traces_plot.getViewBox().setXRange(frame, frame, padding=0)
            self.svd_traces_plot.getViewBox().updateAutoRange()
        self.current_frame_lineedit.setText(str(frame))

    def on_click_keypoints_plot(self, event):
        """
        Update keypoints vtick position when user clicks on keypoints plot
        """
        if event.button() == QtCore.Qt.LeftButton:
            mouse_point = self.keypoints_traces_plot.vb.mapSceneToView(event._scenePos)
            self.update_keypoints_vtick(mouse_point.x())

    def update_keypoints_vtick(self, x_pos=None):
        """
        Update the vertical line indicating the current frame in the plot by setting the x position (x_pos) of the vertical line
        """
        if not self.is_pose_loaded:
            return
        if x_pos is not None:
            self.keypoints_vtick.setPos(x_pos)
            frame = int(x_pos)
        else:
            self.keypoints_vtick.setPos(self.cframe)
            frame = self.cframe
        # Check if x position is within the plot's current range of view
        if (
            not self.keypoints_traces_plot.getViewBox().viewRange()[0][0]
            <= frame
            <= self.keypoints_traces_plot.getViewBox().viewRange()[0][1]
        ):
            self.keypoints_traces_plot.getViewBox().setXRange(frame, frame, padding=0)
            self.keypoints_traces_plot.getViewBox().updateAutoRange()
        self.current_frame_lineedit.setText(str(frame))

    def plot_clicked(self, event):
        items = self.video_window.scene().items(event.scenePos())
        posx = 0
        posy = 0
        iplot = 0
        zoom = False
        zoomImg = False
        choose = False
        if self.loaded:
            for x in items:
                if x == self.keypoints_traces_plot:
                    vb = self.keypoints_traces_plot.vb
                    pos = vb.mapSceneToView(event.scenePos())
                    posx = pos.x()
                    iplot = 1
                elif x == self.svd_traces_plot:
                    vb = self.keypoints_traces_plot.vb
                    pos = vb.mapSceneToView(event.scenePos())
                    posx = pos.x()
                    iplot = 2
                elif x == self.p0:
                    if event.button() == 1:
                        if event.double():
                            zoomImg = True
                if iplot == 1 or iplot == 2:
                    if event.button() == 1:
                        if event.double():
                            zoom = True
                        else:
                            choose = True
        if zoomImg:
            self.p0.setRange(xRange=(0, self.LX), yRange=(0, self.LY))
        if zoom:
            self.keypoints_traces_plot.setRange(xRange=(0, self.nframes))
        if choose:
            if self.playButton.isEnabled() and not self.online_mode:
                self.cframe = np.maximum(
                    0, np.minimum(self.nframes - 1, int(np.round(posx)))
                )
                self.frame_slider.setValue(self.cframe)
                # self.jump_to_frame()

    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Neural data plot ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ ##

    # Open a QDialog to select the neural data to plot
    def load_neural_data(self, prediction_mode=False):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle("Neural activity")
        dialog.setContentsMargins(10, 10, 10, 10)
        dialog.prediction_mode = prediction_mode
        # Set size of the dialog
        if dialog.prediction_mode:
            dialog.setFixedWidth(np.floor(self.sizeObject.width() / 3).astype(int))
            dialog.setFixedHeight(np.floor(self.sizeObject.height() / 4).astype(int))
        else:
            dialog.setFixedWidth(np.floor(self.sizeObject.width() / 3).astype(int))
            dialog.setFixedHeight(np.floor(self.sizeObject.height() / 3).astype(int))

        # Create a vertical layout for the dialog
        vbox = QtWidgets.QVBoxLayout()
        dialog.setLayout(vbox)

        # Create a grouppbox for neural activity and set a vertical layout
        neural_activity_groupbox = QtWidgets.QGroupBox("Neural activity data")
        neural_activity_groupbox.setLayout(QtWidgets.QVBoxLayout())
        neural_activity_groupbox.setStyleSheet(
            "QGroupBox {border: 1px solid gray; border-radius: 9px; margin-top: 0.5em;} "
        )

        # Add a label to the groupbox
        neural_file_groupbox = QtWidgets.QGroupBox()
        neural_file_groupbox.setLayout(QtWidgets.QHBoxLayout())
        neural_file_groupbox.setStyleSheet("QGroupBox { border: 0px solid gray; }")
        neural_data_label = QtWidgets.QLabel("Neural data:")
        neural_file_groupbox.layout().addWidget(neural_data_label)
        # Add a QLineEdit to the groupbox
        dialog.neural_data_lineedit = QtWidgets.QLineEdit()
        dialog.neural_data_lineedit.setReadOnly(True)
        neural_file_groupbox.layout().addWidget(dialog.neural_data_lineedit)
        # Add a QPushButton to the groupbox
        neural_data_button = QtWidgets.QPushButton("Browse...")
        neural_data_button.clicked.connect(
            lambda clicked: self.set_neural_data_filepath(clicked, dialog)
        )
        neural_file_groupbox.layout().addWidget(neural_data_button)
        neural_activity_groupbox.layout().addWidget(neural_file_groupbox)

        """
        # Create a hbox for neural data type selection
        neural_datatype_groupbox = QtWidgets.QGroupBox()
        neural_datatype_groupbox.setLayout(QtWidgets.QHBoxLayout())
        neural_datatype_groupbox.setStyleSheet("QGroupBox { border: 0px solid gray; }")
        # Add a label to the hbox
        neural_data_type_label = QtWidgets.QLabel("Data type:")
        neural_datatype_groupbox.layout().addWidget(neural_data_type_label)
        dialog.neural_data_type_radiobuttons = QtWidgets.QButtonGroup()
        dialog.neural_data_type_radiobuttons.setExclusive(True)
        dialog.calcium_radiobutton = QtWidgets.QRadioButton("Calcium")
        dialog.calcium_radiobutton.setChecked(True)
        dialog.ephys_radiobutton = QtWidgets.QRadioButton("Electrophysiology")
        dialog.neural_data_type_radiobuttons.addButton(dialog.calcium_radiobutton)
        dialog.neural_data_type_radiobuttons.addButton(dialog.ephys_radiobutton)
        # Add QRadiobuttons to the hbox
        neural_datatype_groupbox.layout().addWidget(dialog.calcium_radiobutton)
        neural_datatype_groupbox.layout().addWidget(dialog.ephys_radiobutton)
        neural_activity_groupbox.layout().addWidget(neural_datatype_groupbox)
        """

        # Add a hbox for data visualization
        neural_data_vis_groupbox = QtWidgets.QGroupBox()
        neural_data_vis_groupbox.setLayout(QtWidgets.QHBoxLayout())
        neural_data_vis_groupbox.setStyleSheet("QGroupBox { border: 0px solid gray; }")
        neural_data_vis_label = QtWidgets.QLabel("Data visualization:")
        neural_data_vis_groupbox.layout().addWidget(neural_data_vis_label)
        dialog.neural_data_vis_radiobuttons = QtWidgets.QButtonGroup()
        dialog.neural_data_vis_radiobuttons.setExclusive(True)
        dialog.heatmap_button = QtWidgets.QRadioButton("Heatmap")
        dialog.heatmap_button.setChecked(True)
        dialog.trace_button = QtWidgets.QRadioButton("Traces")
        dialog.neural_data_vis_radiobuttons.addButton(dialog.heatmap_button)
        dialog.neural_data_vis_radiobuttons.addButton(dialog.trace_button)
        # Add QRadiobuttons to the hbox
        neural_data_vis_groupbox.layout().addWidget(dialog.heatmap_button)
        neural_data_vis_groupbox.layout().addWidget(dialog.trace_button)
        neural_activity_groupbox.layout().addWidget(neural_data_vis_groupbox)

        vbox.addWidget(neural_activity_groupbox)

        if not dialog.prediction_mode:
            # Add a timestamps groupbox
            timestamps_groupbox = QtWidgets.QGroupBox("Timestamps (Optional)")
            timestamps_groupbox.setLayout(QtWidgets.QVBoxLayout())
            timestamps_groupbox.setStyleSheet(
                "QGroupBox {border: 1px solid gray; border-radius: 9px; margin-top: 0.5em;} "
            )

            # Add a groupbpx for neural timestamps selection
            neural_data_timestamps_groupbox = QtWidgets.QGroupBox()
            neural_data_timestamps_groupbox.setLayout(QtWidgets.QHBoxLayout())
            neural_data_timestamps_groupbox.setStyleSheet(
                "QGroupBox { border: 0px solid gray; }"
            )
            neural_timestamps_label = QtWidgets.QLabel("Neural timestamps:")
            neural_data_timestamps_groupbox.layout().addWidget(neural_timestamps_label)
            dialog.neural_data_timestamps_lineedit = QtWidgets.QLineEdit()
            dialog.neural_data_timestamps_lineedit.setReadOnly(True)
            neural_data_timestamps_groupbox.layout().addWidget(
                dialog.neural_data_timestamps_lineedit
            )
            neural_timestamps_browse_button = QtWidgets.QPushButton("Browse...")
            neural_timestamps_browse_button.clicked.connect(
                lambda clicked: self.set_neural_timestamps_filepath(clicked, dialog)
            )
            neural_data_timestamps_groupbox.layout().addWidget(
                neural_timestamps_browse_button
            )
            timestamps_groupbox.layout().addWidget(neural_data_timestamps_groupbox)

            """
            neural_time_groupbox = QtWidgets.QGroupBox()
            neural_time_groupbox.setLayout(QtWidgets.QHBoxLayout())
            neural_time_groupbox.setStyleSheet("QGroupBox { border: 0px solid gray; }")
            neural_tstart_label = QtWidgets.QLabel("Start time:")
            neural_time_groupbox.layout().addWidget(neural_tstart_label)
            dialog.neural_tstart_qlineedit = QtWidgets.QLineEdit()
            neural_time_groupbox.layout().addWidget(dialog.neural_tstart_qlineedit)
            neural_tend_label = QtWidgets.QLabel("End time:")
            neural_time_groupbox.layout().addWidget(neural_tend_label)
            dialog.neural_tend_qlineedit = QtWidgets.QLineEdit()
            neural_time_groupbox.layout().addWidget(dialog.neural_tend_qlineedit)
            timestamps_groupbox.layout().addWidget(neural_time_groupbox)
            """

            # Add a groupbpx for behav timestamps selection
            behav_data_timestamps_groupbox = QtWidgets.QGroupBox()
            behav_data_timestamps_groupbox.setLayout(QtWidgets.QHBoxLayout())
            behav_data_timestamps_groupbox.setStyleSheet(
                "QGroupBox { border: 0px solid gray; }"
            )
            behav_timestamps_label = QtWidgets.QLabel("Behavior timestamps:")
            behav_data_timestamps_groupbox.layout().addWidget(behav_timestamps_label)
            dialog.behav_data_timestamps_qlineedit = QtWidgets.QLineEdit()
            dialog.behav_data_timestamps_qlineedit.setReadOnly(True)
            behav_data_timestamps_groupbox.layout().addWidget(
                dialog.behav_data_timestamps_qlineedit
            )
            behav_timestamps_browse_button = QtWidgets.QPushButton("Browse...")
            behav_timestamps_browse_button.clicked.connect(
                lambda clicked: self.set_behav_timestamps_filepath(clicked, dialog)
            )
            behav_data_timestamps_groupbox.layout().addWidget(
                behav_timestamps_browse_button
            )
            timestamps_groupbox.layout().addWidget(behav_data_timestamps_groupbox)

            """
            behav_time_groupbox = QtWidgets.QGroupBox()
            behav_time_groupbox.setLayout(QtWidgets.QHBoxLayout())
            behav_time_groupbox.setStyleSheet("QGroupBox { border: 0px solid gray; }")
            behav_tstart_label = QtWidgets.QLabel("Start time:")
            behav_time_groupbox.layout().addWidget(behav_tstart_label)
            dialog.behav_tstart_qlineedit = QtWidgets.QLineEdit()
            behav_time_groupbox.layout().addWidget(dialog.behav_tstart_qlineedit)
            behav_tend_label = QtWidgets.QLabel("End time:")
            behav_time_groupbox.layout().addWidget(behav_tend_label)
            dialog.behav_tend_qlineedit = QtWidgets.QLineEdit()
            behav_time_groupbox.layout().addWidget(dialog.behav_tend_qlineedit)
            timestamps_groupbox.layout().addWidget(behav_time_groupbox)
            """

            vbox.addWidget(timestamps_groupbox)

            # Add a hbox for cancel and done buttons
            neural_data_buttons_hbox = QtWidgets.QHBoxLayout()
            # Add a cancel button
            neural_data_cancel_button = QtWidgets.QPushButton("Cancel")
            neural_data_cancel_button.clicked.connect(dialog.reject)
            neural_data_buttons_hbox.addWidget(neural_data_cancel_button)
            # Add a done button
            neural_data_done_button = QtWidgets.QPushButton("Done")
            neural_data_done_button.clicked.connect(
                lambda clicked: self.set_neural_data(clicked, dialog)
            )
            neural_data_buttons_hbox.addWidget(neural_data_done_button)
            vbox.addLayout(neural_data_buttons_hbox)

        else:
            # Add a hbox for cancel and done buttons
            buttons_hbox = QtWidgets.QHBoxLayout()
            # Add a cancel button
            cancel_button = QtWidgets.QPushButton("Cancel")
            cancel_button.clicked.connect(dialog.reject)
            buttons_hbox.addWidget(cancel_button)
            # Add a done button
            done_button = QtWidgets.QPushButton("Done")
            done_button.clicked.connect(
                lambda clicked: self.set_neural_prediction_data(clicked, dialog)
            )
            buttons_hbox.addWidget(done_button)
            vbox.addLayout(buttons_hbox)

        dialog.exec_()

    def set_neural_data_filepath(self, clicked, dialog):
        """
        Set the neural data file
        """
        neural_data_file = io.load_npy_file(self)
        dialog.neural_data_lineedit.setText(neural_data_file)

    def set_neural_timestamps_filepath(self, clicked, dialog):
        """
        Set the neural timestamps file
        """
        neural_timestamps_file = io.load_npy_file(self)
        dialog.neural_data_timestamps_lineedit.setText(neural_timestamps_file)

    def set_behav_timestamps_filepath(self, clicked, dialog):
        """
        Set the behavioral data file
        """
        behav_data_file = io.load_npy_file(self)
        dialog.behav_data_timestamps_qlineedit.setText(behav_data_file)

    def set_neural_data(self, clicked, dialog):
        """
        Get user settings from the dialog box to set neural activity data
        """
        neural_data_filepath = dialog.neural_data_lineedit.text()
        """
        if dialog.calcium_radiobutton.isChecked():
            neural_data_type = "calcium"
        else:
            neural_data_type = "ephys"
        """
        if dialog.heatmap_button.isChecked():
            data_viz_method = "heatmap"
        else:
            data_viz_method = "lineplot"
        neural_timestamps_filepath = dialog.neural_data_timestamps_lineedit.text()
        # neural_tstart = dialog.neural_tstart_qlineedit.text()
        # neural_tend = dialog.neural_tend_qlineedit.text()
        behav_data_timestamps_filepath = dialog.behav_data_timestamps_qlineedit.text()
        # behav_tstart = dialog.behav_tstart_qlineedit.text()
        # behav_tend = dialog.behav_tend_qlineedit.text()
        print("neural_data_filepath:", neural_data_filepath)
        print("data_viz_type:", data_viz_method)
        print("neural_timestamps_filepath:", neural_timestamps_filepath)
        print("behav_data_timestamps_filepath:", behav_data_timestamps_filepath)
        print("\n")
        self.neural_activity.set_data(
            neural_data_filepath,
            None,
            data_viz_method,
            neural_timestamps_filepath,
            None,
            None,
            behav_data_timestamps_filepath,
            None,
            None,
        )
        self.neural_data_loaded = True
        self.plot_neural_data()
        dialog.accept()

    def set_neural_prediction_data(self, clicked, dialog):
        """
        Get user settings from the dialog box to set neural prediction data
        """
        neural_data_filepath = dialog.neural_data_lineedit.text()
        """
        if dialog.calcium_radiobutton.isChecked():
            neural_data_type = "calcium"
        else:
            neural_data_type = "ephys"
        """
        if dialog.heatmap_button.isChecked():
            data_viz_method = "heatmap"
        else:
            data_viz_method = "lineplot"
        print("neural_data_filepath:", neural_data_filepath)
        print("data_viz_type:", data_viz_method)
        print("\n")
        self.neural_predictions.set_data(neural_data_filepath, None, data_viz_method)
        self.neural_predictions_loaded = True
        self.plot_neural_predictions()
        dialog.accept()

    def plot_neural_data(self):
        # Clear plot
        self.neural_activity_plot.clear()

        # Note: neural data is of shape (neurons, time)
        # Create a heatmap for the neural data and add it to plot 1
        vmin = -np.percentile(self.neural_activity.data, 95)
        vmax = np.percentile(self.neural_activity.data, 95)

        if self.neural_activity.data_viz_method == "heatmap":
            self.neural_heatmap = pg.ImageItem(
                self.neural_activity.data, autoDownsample=True, levels=(vmin, vmax)
            )
            if (
                self.neural_activity.behavior_timestamps is not None
                and self.neural_activity.neural_timestamps is not None
            ):
                extent = QtCore.QRect(
                    self.neural_activity.neural_timestamps_resampled[0],
                    0,
                    self.neural_activity.neural_timestamps_resampled[-1],
                    self.nframes,
                )
                self.neural_heatmap.setRect(extent)
            self.neural_activity_plot.addItem(self.neural_heatmap)
            colormap = cm.get_cmap("gray_r")
            colormap._init()
            lut = (colormap._lut * 255).view(
                np.ndarray
            )  # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
            lut = lut[0:-3, :]
            # apply the colormap
            self.neural_heatmap.setLookupTable(lut)
        else:
            x = np.empty(
                (self.neural_activity.data.shape[0], self.neural_activity.data.shape[1])
            )
            x[:] = np.arange(self.neural_activity.data.shape[1])[np.newaxis, :]
            y = self.neural_activity.data
            neural_lineplot = guiparts.MultiLine(x, y)
            self.neural_activity_plot.addItem(neural_lineplot)
        self.neural_activity_plot.autoRange()
        # Add a vertical line to the plot to indicate the time of the current trial
        self.neural_activity_vtick = pg.InfiniteLine(
            pos=self.cframe,
            angle=90,
            pen=pg.mkPen(color=(255, 0, 0), width=2, movable=True),
        )
        self.neural_activity_plot.addItem(self.neural_activity_vtick)
        self.neural_activity_plot.setXRange(0, self.neural_activity.data.shape[1])
        self.neural_activity_plot.setLimits(xMin=0, xMax=self.nframes)

        self.update_status_bar("Neural data loaded")

    def plot_neural_predictions(self):
        # Clear plot
        self.neural_predictions_plot.clear()

        # Create a heatmap for the neural data and add it to plot 1
        vmin = -np.percentile(self.neural_predictions.data, 95)
        vmax = np.percentile(self.neural_predictions.data, 95)

        if self.neural_predictions.data_viz_method == "heatmap":
            self.neural_heatmap = pg.ImageItem(
                self.neural_predictions.data, autoDownsample=True, levels=(vmin, vmax)
            )
            # TODO - Use same resampling as neural data
            # if self.neural_activity.behavior_timestamps is not None and self.neural_activity.neural_timestamps is not None:
            #    extent = QtCore.QRect(0, 0, self.neural_activity.behavior_timestamps.shape[0], self.neural_activity.data.shape[0])
            #    self.neural_heatmap.setRect(extent)
            self.neural_predictions_plot.addItem(self.neural_heatmap)
            colormap = cm.get_cmap("gray_r")
            colormap._init()
            lut = (colormap._lut * 255).view(
                np.ndarray
            )  # Convert matplotlib colormap from 0-1 to 0 -255 for Qt
            lut = lut[0:-3, :]
            # apply the colormap
            self.neural_heatmap.setLookupTable(lut)
        else:
            x = np.empty(
                (
                    self.neural_predictions.data.shape[0],
                    self.neural_predictions.data.shape[1],
                )
            )
            x[:] = np.arange(self.neural_predictions.data.shape[1])[np.newaxis, :]
            y = self.neural_predictions.data
            neural_lineplot = guiparts.MultiLine(x, y)
            self.neural_predictions_plot.addItem(neural_lineplot)
        self.neural_predictions_plot.autoRange()
        # Add a vertical line to the plot to indicate the time of the current trial
        if self.neural_predictions_vtick is None:
            self.neural_predictions_vtick = pg.InfiniteLine(
                pos=self.cframe,
                angle=90,
                pen=pg.mkPen(color=(255, 0, 0), width=2, movable=True),
            )
        self.neural_predictions_plot.addItem(self.neural_predictions_vtick)
        self.neural_predictions_plot.setXRange(0, self.neural_predictions.data.shape[1])
        self.neural_predictions_plot.setLimits(xMin=0, xMax=self.nframes)

    def on_click_neural_activity_plot(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            mouse_point = self.neural_activity_plot.vb.mapSceneToView(event._scenePos)
            self.update_neural_data_vtick(mouse_point.x())

    def on_click_neural_predictions_plot(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            mouse_point = self.neural_predictions_plot.vb.mapSceneToView(
                event._scenePos
            )
            self.update_neural_predictions_vtick(mouse_point.x())

    def update_neural_predictions_vtick(self, x_pos=None):
        """
        Update the vertical line indicating the current frame in the neural predictions plot by setting the x position (x_pos) of the line
        """
        if not self.neural_predictions_loaded:
            return
        if x_pos is not None:
            self.neural_predictions_vtick.setPos(x_pos)
            frame = int(x_pos)
        else:
            self.neural_predictions_vtick.setPos(self.cframe)
            frame = self.cframe
        # Check if x position is within the neural activity plot's current range of view
        if (
            not self.neural_predictions_plot.getViewBox().viewRange()[0][0]
            <= frame
            <= self.neural_predictions_plot.getViewBox().viewRange()[0][1]
        ):
            self.neural_predictions_plot.getViewBox().setXRange(frame, frame, padding=0)
            self.neural_predictions_plot.getViewBox().updateAutoRange()
        self.current_frame_lineedit.setText(str(frame))

    def update_neural_data_vtick(self, x_pos=None):
        """
        Update the vertical line indicating the current frame in the neural data plot by setting the x position (x_pos) of the line
        """
        if not self.neural_data_loaded:
            return
        if x_pos is not None:
            self.neural_activity_vtick.setPos(x_pos)
            frame = int(x_pos)
        else:
            self.neural_activity_vtick.setPos(self.cframe)
            frame = self.cframe
        # Check if x position is within the neural activity plot's current range of view
        if (
            not self.neural_activity_plot.getViewBox().viewRange()[0][0]
            <= frame
            <= self.neural_activity_plot.getViewBox().viewRange()[0][1]
        ):
            self.neural_activity_plot.getViewBox().setXRange(frame, frame, padding=0)
            self.neural_activity_plot.getViewBox().updateAutoRange()
        self.current_frame_lineedit.setText(str(frame))

    def update_behavior_data(self):
        """
        Update the behavior data such that it is resampled to neural timescale
        """
        behav_resampled_idx = self.neural_predictions.behavior_timestamps_resampled
        # Resample video data

        # Resample pose
        if self.is_pose_loaded:
            self.pose_x_coord[0] = self.pose_x_coord[0][:, behav_resampled_idx]
            self.pose_y_coord[0] = self.pose_y_coord[0][:, behav_resampled_idx]
            self.pose_likelihood[0] = self.pose_likelihood[0][:, behav_resampled_idx]
            self.plot_trace(
                wplot=1,
                proctype=5,
                wroi=None,
                color=None,
                keypoints_group_selected="eye(back)",
            )
            self.update_status_bar("Pose data resampled")

    ### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Clustering and ROI ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def vis_combobox_selection_changed(self):
        """
        Call clustering or ROI display functions upon user selection from combo box
        """
        self.clear_visualization_window()
        visualization_request = int(self.roi_embed_combobox.currentIndex())
        self.reflector.show()
        if visualization_request == 1:  # ROI
            self.cluster_model.disable_data_clustering_features(self)
            if len(self.ROIs) > 0:
                self.update_ROI_vis_comboBox()
                self.update_status_bar("")
            else:
                self.update_status_bar("Please add ROIs for display")
        elif visualization_request == 2 or visualization_request == 3:  # tSNE/UMAP
            self.reflector.hide()
            self.cluster_model.enable_data_clustering_features(parent=self)
            self.update_status_bar("")
        else:
            self.cluster_model.disable_data_clustering_features(self)

    def clear_visualization_window(self):
        self.roi_display_combobox.hide()
        self.pROIimg.clear()
        self.pROI.removeItem(self.scatter)
        self.clustering_plot.clear()
        self.clustering_plot.hideAxis("left")
        self.clustering_plot.hideAxis("bottom")
        self.clustering_plot.removeItem(self.clustering_scatterplot)
        self.clustering_plot_legend.setParentItem(None)
        self.clustering_plot_legend.hide()

    def cluster_plot_zoom_buttons(self, in_or_out):
        """
        see ViewBox.scaleBy()
        pyqtgraph wheel zoom is s = ~0.75
        """
        s = 0.9
        zoom = (s, s) if in_or_out == "in" else (1 / s, 1 / s)
        self.clustering_plot.vb.scaleBy(zoom)

    def update_ROI_vis_comboBox(self):
        """
        Update ROI selection combo box
        """
        self.roi_display_combobox.clear()
        self.pROIimg.clear()
        self.roi_display_combobox.addItem("--Type--")
        for i in range(len(self.ROIs)):
            selected = self.ROIs[i]
            self.roi_display_combobox.addItem(
                str(selected.iROI + 1) + ". " + selected.rtype
            )
        if self.roi_embed_combobox.currentText() == "ROI":
            self.roi_display_combobox.show()

    def display_ROI(self):
        """
        Plot selected ROI on visualizaiton window
        """
        self.roi_display_combobox.show()
        roi_request = self.roi_display_combobox.currentText()
        if roi_request != "--Type--":
            self.pROI.addItem(self.scatter)
            roi_request_ind = int(roi_request.split(".")[0]) - 1
            self.ROIs[int(roi_request_ind)].plot(self)
            # self.set_ROI_saturation_label(self.ROIs[int(roi_request_ind)].saturation)
        else:
            self.pROIimg.clear()
            self.pROI.removeItem(self.scatter)

    def highlight_embed_point(self, playback_point):
        x = [np.array(self.clustering_scatterplot.points()[playback_point].pos().x())]
        y = [np.array(self.clustering_scatterplot.points()[playback_point].pos().y())]
        self.clustering_highlight_scatterplot.setData(
            x=x,
            y=y,
            symbol="x",
            brush="r",
            pxMode=True,
            hoverable=True,
            hoverSize=20,
            hoverSymbol="x",
            hoverBrush="r",
            pen=(0, 0, 0, 0),
            data=playback_point,
            size=15,
        )
        """
        old = self.clustering_scatterplot.data['hovered']
        self.clustering_scatterplot.data['sourceRect'][old] = 1
        bool_mask = np.full((len(self.clustering_scatterplot.data)), False, dtype=bool)
        self.clustering_scatterplot.data['hovered'] = bool_mask
        self.clustering_scatterplot.invalidate()   
        self.clustering_scatterplot.updateSpots()
        self.clustering_scatterplot.sigPlotChanged.emit(self.clustering_scatterplot)

        bool_mask[playback_point] = True
        self.clustering_scatterplot.data['hovered'] = bool_mask
        self.clustering_scatterplot.data['sourceRect'][bool_mask] = 0
        self.clustering_scatterplot.updateSpots()   
        #points = self.clustering_scatterplot.points()
        #self.clustering_scatterplot.sigClicked.emit([points[playback_point]], None, self)
        """

    ### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Popups/QMessageboxes ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    def load_video_popup(self):
        # Open a qmessage box to notify the user that the video is not loaded
        msg = QtWidgets.QMessageBox()
        # Error icon in the top left corner
        msg.setIcon(QtWidgets.QMessageBox.Critical)
        msg.setText("Please load a video first.")
        msg.setWindowTitle("No video loaded")
        msg.exec_()

    def invalid_trace_popup(self):
        # Open a qmessagebox to notify the user that the data is not 1D
        msgBox = QtWidgets.QMessageBox(self)
        msgBox.setText("Please select a 1D trace")
        msgBox.setWindowTitle("Invalid trace")
        msgBox.exec_()

    def invalid_roi_popup(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setText("only pupil ROI allowed during online mode")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def select_roi_popup(self):
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Warning)
        msg.setText("Please select a ROI")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def model_loaded_popup(self, model_path):
        # Open a qmessagebox to notify the user that the model has been loaded and the user has to select ok to continue
        msgBox = QtWidgets.QMessageBox(self)
        msgBox.setText("Model loaded from: " + model_path)
        msgBox.setWindowTitle("Model loaded")
        msgBox.exec_()

    def update_window_title(self, title=None):
        if title is None:
            self.setWindowTitle("Facemap")
        else:
            self.setWindowTitle("Facemap: " + title)


### ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ Main ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


def run(moviefile=None, savedir=None):
    # Always start by initializing Qt (only once per application)
    app = QtWidgets.QApplication(sys.argv)
    icon_path = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), "../mouse.png"
    )
    app_icon = QIcon()
    app_icon.addFile(icon_path, QtCore.QSize(16, 16))
    app_icon.addFile(icon_path, QtCore.QSize(24, 24))
    app_icon.addFile(icon_path, QtCore.QSize(32, 32))
    app_icon.addFile(icon_path, QtCore.QSize(48, 48))
    app_icon.addFile(icon_path, QtCore.QSize(96, 96))
    app_icon.addFile(icon_path, QtCore.QSize(256, 256))
    app.setWindowIcon(app_icon)
    GUI = MainW(moviefile, savedir)
    ret = app.exec_()
    sys.exit(ret)
