" Test imports for facemap package "


def test_facemap_imports():
    import facemap
    from facemap import (
        keypoints,
        process,
        pupil,
        roi,
        running,
        utils,
    )


def test_gui_imports():
    from facemap.gui import gui, guiparts, help_windows, io, menus, cluster


def test_neural_prediction_imports():
    from facemap.neural_prediction import (
        neural_activity,
        neural_model,
        prediction_utils,
    )


def test_pose_imports():
    from facemap.pose import (
        datasets,
        facemap_network,
        model_loader,
        model_training,
        pose,
        pose_gui,
        pose_helper_functions,
        refine_pose,
        transforms,
    )
