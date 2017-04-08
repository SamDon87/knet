import logging

import joblib
import numpy as np
import pandas as pd
import os
from nms_network import model as nms_net
from tools import nms, metrics
from data import get_frame_data_fixed

def softmax(logits):
    n_classes = logits.shape[1]
    return np.exp(logits) / np.tile(np.sum(np.exp(logits),
                                           axis=1).reshape(-1, 1), [1, n_classes])

def eval_model(sess,
               nnms_model,
               detections_dir,
               labels_dir,
               eval_frames,
               n_bboxes,
               n_features,
               global_step,
               out_dir,
               nms_thres=0.5,
               gt_match_iou_thres=0.7,
               det_thres=0.001):

    if not os.path.exists(out_dir):
        os.makedirs(out_dir)

    inference_orig_all = []

    losses = []

    eval_data_orig = []
    eval_data_orig_nms = []
    eval_data_filtered = []
    eval_data_filter_only = []
    eval_data_oracle = []
    info_data_all = []


    for fid in eval_frames:

        frame_data = get_frame_data_fixed(frame_id=fid,
                                    labels_dir=labels_dir,
                                    detections_dir=detections_dir,
                                    n_detections=n_bboxes,
                                    n_features=n_features)

        feed_dict = {nnms_model.dt_coords: frame_data['dt_coords'],
                     nnms_model.dt_features: frame_data['dt_features'],
                     nnms_model.dt_probs_ini: frame_data['dt_probs'],
                     nnms_model.gt_coords: frame_data['gt_coords'],
                     nnms_model.gt_labels: frame_data['gt_labels'],
                     nnms_model.keep_prob: 1.0}

        inference_orig = frame_data['dt_probs']
        inference_orig_all.append(inference_orig)

        inference_filtered, inference_filter, inference_oracle,  dt_dt_iou, loss = sess.run(
            [nnms_model.class_scores, nnms_model.sigmoid, nnms_model.det_labels,
             nnms_model.iou_feature, nnms_model.loss], feed_dict=feed_dict)

        losses.append(loss)

        is_suppressed_orig = nms.nms_all_classes(
            dt_dt_iou, inference_orig, iou_thr=nms_thres)

        dt_coords_xywh = frame_data['dt_coords']
        dt_coords_xywh[:, 2] = dt_coords_xywh[:, 2] - dt_coords_xywh[:, 0]
        dt_coords_xywh[:, 3] = dt_coords_xywh[:, 3] - dt_coords_xywh[:, 1]
        frame_col = (fid+1) * np.ones([len(dt_coords_xywh), 1])

        data_orig = np.hstack([frame_col, dt_coords_xywh, inference_orig])
        eval_data_orig.append(data_orig)
        data_orig_nms = np.copy(data_orig)
        data_orig_nms[np.where(is_suppressed_orig == True)[0], 5] = 0
        eval_data_orig_nms.append(data_orig_nms)

        data_filtered = np.hstack([frame_col, dt_coords_xywh, inference_filtered])
        data_filter_only = np.hstack([frame_col, dt_coords_xywh, inference_filter])
        eval_data_filtered.append(data_filtered)
        eval_data_filter_only.append(data_filter_only)

        data_oracle = np.hstack([frame_col, dt_coords_xywh, inference_oracle])
        eval_data_oracle.append(data_oracle)

        info_data = np.hstack([frame_col, dt_coords_xywh, inference_orig,
                               is_suppressed_orig, inference_oracle,
                               inference_filter, inference_filtered])
        info_data_all.append(info_data)

    mean_loss = np.mean(losses)

    logging.info('loss : %f' % mean_loss)

    eval_data_orig = np.vstack(eval_data_orig)
    out_file_orig = os.path.join(out_dir, 'kitti_car_mscnn_nonms_' + str(global_step) + '.txt')
    np.savetxt(out_file_orig, eval_data_orig, fmt='%.6f', delimiter=',')

    eval_data_orig_nms = np.vstack(eval_data_orig_nms)
    out_file_orig_nms = os.path.join(out_dir, 'kitti_car_mscnn_nms_' + str(global_step) + '.txt')
    np.savetxt(out_file_orig_nms, eval_data_orig_nms, fmt='%.6f', delimiter=',')

    eval_data_filtered = np.vstack(eval_data_filtered)
    out_filer_only = os.path.join(out_dir, 'kitti_car_mscnn_knet_filtered_' + str(global_step) + '.txt')
    np.savetxt(out_filer_only, eval_data_filtered, fmt='%.6f', delimiter=',')

    eval_data_filter_only = np.vstack(eval_data_filter_only)
    out_file_filter_only = os.path.join(out_dir, 'kitti_car_mscnn_knet_filters_only_' + str(global_step) + '.txt')
    np.savetxt(out_file_filter_only, eval_data_filter_only, fmt='%.6f', delimiter=',')

    eval_data_oracle = np.vstack(eval_data_oracle)
    out_file_oracle = os.path.join(out_dir, 'kitti_car_mscnn_knet_oracle_' + str(global_step) + '.txt')
    np.savetxt(out_file_oracle, eval_data_oracle, fmt='%.6f', delimiter=',')

    info_data_all = np.vstack(info_data_all)
    info_data_all = pd.DataFrame(info_data_all,
                                 columns=['frame_id', 'x', 'y', 'w', 'h',
                                          'inference_orig', 'is_suppressed_orig',
                                          'true_label', 'fnet_filter_value',
                                          'fnet_orig_combination'])

    out_file_info = os.path.join(out_dir, 'kitti_car_mscnn_info_data_' + str(global_step) + '.csv')
    import ipdb; ipdb.set_trace()

    info_data_all.to_csv(out_file_info)

    return mean_loss
