"""Training routine for knet trained on top of MS-CNN inference on KITTI object detection data

"""

import logging
from timeit import default_timer as timer

import gflags
import ntpath
import numpy as np
from numpy.random import RandomState

import os
import tensorflow as tf
from google.apputils import app
from nms_network import model as nms_net
import eval
from data import get_frame_data, get_frame_data_fixed
from tools import experiment_config as expconf


gflags.DEFINE_string('data_dir', None, 'directory containing train data')
gflags.DEFINE_string('root_log_dir', None, 'root directory to save logs')
gflags.DEFINE_string('config_path', None, 'path to experiment config')

FLAGS = gflags.FLAGS

CAR_CLASSES = {'Car': 0, 'Van': 1, 'Truck': 2, 'Tram': 3}


def shuffle_samples(n_frames):
    return np.random.choice(n_frames, n_frames, replace=False)


def input_ops(n_dt_features, n_classes):

    input_dict = {}
    n_dt_coords = 4
    input_dict['dt_coords'] = tf.placeholder(
        tf.float32, shape=[
                None, n_dt_coords])

    input_dict['dt_features'] = tf.placeholder(tf.float32,
                                 shape=[
                                     None,
                                     n_classes+n_dt_features])

    input_dict['dt_probs'] = tf.placeholder(tf.float32,
                                 shape=[
                                     None,
                                     n_classes])

    input_dict['gt_coords'] = tf.placeholder(tf.float32, shape=[None, 4])

    input_dict['gt_labels'] = tf.placeholder(tf.float32, shape=None)

    input_dict['nms_labels'] = tf.placeholder(tf.float32, shape=None)

    input_dict['keep_prob'] = tf.placeholder(tf.float32)

    return input_dict


def mean_loss(sess, nms_model, frames,
              labels_dir, detection_dir,
              n_bboxes_test, n_dt_features,
              n_frames=100):

    losses = []

    for tfid in frames[0:n_frames]:

        frame_data = get_frame_data_fixed(frame_id=tfid,
                                    labels_dir=labels_dir,
                                    detections_dir=detection_dir,
                                    n_detections=n_bboxes_test,
                                    n_features=n_dt_features)

        feed_dict = {nms_model.dt_coords: frame_data['dt_coords'],
                     nms_model.dt_features: frame_data['dt_features'],
                     nms_model.dt_probs_ini: frame_data['dt_probs'],
                     nms_model.gt_coords: frame_data['gt_coords'],
                     nms_model.gt_labels: frame_data['gt_labels'],
                     # nnms_model.nms_labels: frame_data['nms_labels'],
                     nms_model.keep_prob: 1.0}

        det_loss = sess.run([nms_model.det_loss], feed_dict=feed_dict)

        losses.append(det_loss)

    return np.mean(losses)


def write_scalar_summary(value, name, summary_writer, step_id):
    test_map_summ = tf.Summary(
        value=[
            tf.Summary.Value(
                tag=name,
                simple_value=value),
        ])
    summary_writer.add_summary(
        test_map_summ, global_step=step_id)
    return


def main(_):

    config = expconf.ExperimentConfig(data_dir=FLAGS.data_dir,
                                      root_log_dir=FLAGS.root_log_dir,
                                      config_path=FLAGS.config_path)



    logging.info("config info : %s" % config.config)

    labels_dir = os.path.join(FLAGS.data_dir, 'label_2')

    detections_dir = os.path.join(FLAGS.data_dir, 'detection_2')

    frames_ids = np.asarray([int(ntpath.basename(path).split('.')[0]) for path in os.listdir(labels_dir)])

    n_frames = len(frames_ids)
    n_bboxes_test = config.n_bboxes
    n_classes = 1
    class_name = config.general_params.get('class_of_interest', 'Car')
    half = n_frames/2
    learning_rate = config.learning_rate_det

    # shuffled_samples = shuffle_samples(n_frames)
    # train_frames = frames_ids[shuffled_samples[0:half]]

    # test_frames = frames_ids[shuffled_samples[half:]]

    train_frames_path = os.path.join(FLAGS.data_dir, 'train.txt')
    train_frames = np.loadtxt(train_frames_path, dtype=int)

    test_frames_path = os.path.join(FLAGS.data_dir, 'val.txt')
    test_frames = np.loadtxt(test_frames_path, dtype=int)

    train_out_dir = os.path.join(config.log_dir, 'train')
    test_out_dir = os.path.join(config.log_dir, 'test')
    n_train_samples = len(train_frames)
    n_test_samples = len(test_frames)

    logging.info('building model graph..')

    in_ops = input_ops(config.n_dt_features, n_classes)

    nnms_model = nms_net.NMSNetwork(n_classes=1,
                                    input_ops=in_ops,
                                    class_ix=0,
                                    **config.nms_network_config)

    saver = tf.train.Saver(max_to_keep=5, keep_checkpoint_every_n_hours=1.0)

    config.save_results()

    logging.info('training started..')

    with tf.Session() as sess:

        sess.run(nnms_model.init_op)

        step_id = 0
        step_times = []
        data_times = []

        # loss_mode = 'nms'
        # nnms_model.switch_loss('nms')
        # logging.info("current loss mode : %s" % loss_mode)

        summary_writer = tf.summary.FileWriter(config.log_dir, sess.graph)

        for epoch_id in range(0, config.n_epochs):

            epoch_frames = train_frames[shuffle_samples(n_train_samples)]

            for fid in epoch_frames:

                # if step_id == config.loss_change_step:
                #     learning_rate = config.learning_rate_det
                #     loss_mode = 'detection'
                #     nnms_model.switch_loss('detection')
                #     logging.info('switching loss to actual detection loss..')
                #     logging.info('learning rate to %f' % learning_rate)

                start_step = timer()

                frame_data = get_frame_data_fixed(frame_id=fid,
                                            labels_dir=labels_dir,
                                            detections_dir=detections_dir,
                                            n_detections=config.n_bboxes,
                                            class_name=class_name,
                                            n_features=config.n_dt_features)
                data_step = timer()

                feed_dict = {nnms_model.dt_coords: frame_data['dt_coords'],
                             nnms_model.dt_features: frame_data['dt_features'],
                             nnms_model.dt_probs_ini: frame_data['dt_probs'],
                             nnms_model.gt_coords: frame_data['gt_coords'],
                             nnms_model.gt_labels: frame_data['gt_labels'],
                             nnms_model.keep_prob: config.keep_prob_train}

                if nnms_model.loss_type == 'nms':
                    summary,  _ = sess.run([nnms_model.merged_summaries,
                                           nnms_model.nms_train_step],
                                          feed_dict=feed_dict)
                else:
                    summary,  _ = sess.run([nnms_model.merged_summaries,
                                           nnms_model.det_train_step],
                                          feed_dict=feed_dict)

                step_id += 1

                summary_writer.add_summary(summary, global_step=step_id)
                summary_writer.flush()

                end_step = timer()
                step_times.append(end_step-start_step)
                data_times.append(data_step-start_step)

                if step_id % config.eval_step == 0:

                    logging.info("learning rate %s" % str(nnms_model.learning_rate_det.eval()))

                    logging.info('curr step : %d, mean time for step : %s, for getting data : %s' % (step_id,
                                                                                                     str(np.mean(step_times)),
                                                                                                     str(np.mean(data_times))))


                    logging.info("eval on TRAIN..")
                    train_loss_opt, train_loss_fin = eval.eval_model(sess,
                                                 nnms_model,
                                                 detections_dir=detections_dir,
                                                 labels_dir=labels_dir,
                                                 eval_frames=train_frames,
                                                 n_bboxes=config.n_bboxes,
                                                 n_features=config.n_dt_features,
                                                 global_step=step_id,
                                                 out_dir=train_out_dir,
                                                 nms_thres=config.nms_thres,
                                                 class_name=class_name)

                    logging.info("eval on TEST..")
                    test_loss_opt, test_loss_fin = eval.eval_model(sess,
                                                nnms_model,
                                                detections_dir=detections_dir,
                                                labels_dir=labels_dir,
                                                eval_frames=test_frames,
                                                n_bboxes=config.n_bboxes,
                                                n_features=config.n_dt_features,
                                                global_step=step_id,
                                                out_dir=test_out_dir,
                                                nms_thres=config.nms_thres,
                                                class_name=class_name)

                    config.update_results(step_id,
                                          train_loss_opt,
                                          train_loss_fin,
                                          test_loss_opt,
                                          test_loss_fin,
                                          np.mean(step_times))

                    config.save_results()

                    saver.save(sess, config.model_file, global_step=step_id)

        train_loss_opt, train_loss_fin = eval.eval_model(sess,
                                     nnms_model,
                                     detections_dir=detections_dir,
                                     labels_dir=labels_dir,
                                     eval_frames=train_frames,
                                     n_bboxes=config.n_bboxes,
                                     n_features=config.n_dt_features,
                                     global_step=step_id,
                                     out_dir=train_out_dir,
                                     nms_thres=config.nms_thres,
                                     class_name=class_name)

        test_loss_opt, test_loss_fin = eval.eval_model(sess,
                                    nnms_model,
                                    detections_dir=detections_dir,
                                    labels_dir=labels_dir,
                                    eval_frames=test_frames,
                                    n_bboxes=config.n_bboxes,
                                    n_features=config.n_dt_features,
                                    global_step=step_id,
                                    out_dir=test_out_dir,
                                    nms_thres=config.nms_thres,
                                    class_name=class_name)

        config.update_results(step_id,
                              train_loss_opt,
                              train_loss_fin,
                              test_loss_opt,
                              test_loss_fin,
                              np.mean(step_times))

        config.save_results()
        saver.save(sess, config.model_file, global_step=step_id)
    return

if __name__ == '__main__':
    gflags.mark_flag_as_required('data_dir')
    gflags.mark_flag_as_required('root_log_dir')
    gflags.mark_flag_as_required('config_path')
    app.run()
