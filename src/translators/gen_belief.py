import net

import tensorflow as tf

class GenBeliefTranslator(object):
    def build(self, task, reconst_ph, channel, model, config):
        with tf.variable_scope("belief_translator") as scope:
            #t_xb_rs = tf.reshape(
            #        reconst_ph.t_xb,
            #        (config.trainer.n_batch_episodes, 1, task.n_features))
            t_xa_true_rs = tf.reshape(
                    reconst_ph.t_xa_true,
                    (config.trainer.n_batch_episodes, 1, task.n_features))
            #t_xb_tile = tf.tile(
            #        t_xb_rs, (1, config.trainer.n_distractors + 1, 1))
            t_xa = tf.concat(1, (t_xa_true_rs, reconst_ph.t_xa_noise))

            with tf.variable_scope("model") as model_scope:
                t_mean, self.v_model = net.mlp(
                        reconst_ph.t_xa_true,
                        (config.translator.n_hidden, config.channel.n_msg))
                self.t_model_loss = tf.reduce_mean(tf.reduce_sum(
                        tf.square(t_mean - reconst_ph.t_z), axis=1))

                model_scope.reuse_variables()
                t_all_mean, _ = net.mlp(
                        t_xa, (config.translator.n_hidden, config.channel.n_msg))
                t_model_raw_belief = tf.reduce_sum(
                        tf.square(t_all_mean-tf.expand_dims(reconst_ph.t_z, 1)),
                        axis=2)
                #self.t_model_belief = tf.nn.softmax(t_model_raw_belief)
                t_model_rs_belief = tf.nn.softmax(tf.reshape(
                        t_model_raw_belief, (1, -1)))
                t_model_belief = tf.reshape(
                        t_model_rs_belief,
                        (config.trainer.n_batch_episodes,
                            config.trainer.n_distractors + 1))
                t_model_belief_norm = t_model_belief / tf.reduce_max(t_model_belief)
                self.t_model_belief = t_model_belief_norm

            with tf.variable_scope("desc") as desc_scope:
                t_indices = tf.constant(
                        [[i] * task.max_desc_len 
                            for i in range(config.trainer.n_batch_episodes)])
                t_desc_indexed = tf.pack((t_indices, reconst_ph.t_desc), axis=2)
                t_dist, self.v_desc = net.mlp(
                        reconst_ph.t_xa_true,
                        (config.translator.n_hidden, task.n_vocab))
                t_dist_norm = tf.nn.log_softmax(t_dist)
                t_logprobs = tf.gather_nd(t_dist_norm, t_desc_indexed)
                self.t_desc_loss = -tf.reduce_mean(tf.reduce_sum(
                        t_logprobs, axis=1))

                desc_scope.reuse_variables()
                t_all_indices = tf.constant(
                        [[[[i, d]] * task.max_desc_len for d in range(
                                config.trainer.n_distractors + 1)] 
                            for i in range(config.trainer.n_batch_episodes)])
                t_desc_tile = tf.tile(
                        tf.reshape(
                            reconst_ph.t_desc,
                            (config.trainer.n_batch_episodes, 1,
                                task.max_desc_len, 1)),
                        (1, config.trainer.n_distractors + 1, 1, 1))
                t_desc_all_indexed = tf.concat(3, (t_all_indices, t_desc_tile))
                t_all_dist, _ = net.mlp(
                        t_xa, (config.translator.n_hidden, task.n_vocab))
                t_all_dist_norm = tf.nn.log_softmax(t_all_dist)
                t_all_logprobs = tf.gather_nd(t_all_dist_norm, t_desc_all_indexed)
                t_all_scores = tf.reduce_sum(t_all_logprobs, axis=2)
                #self.t_desc_belief = tf.nn.softmax(t_all_scores)
                t_desc_belief_raw = tf.nn.softmax(tf.reshape(
                        t_all_scores, (1, -1)))
                t_desc_belief = tf.reshape(
                        t_desc_belief_raw,
                        (config.trainer.n_batch_episodes,
                            config.trainer.n_distractors + 1))
                t_desc_belief_norm = t_desc_belief / tf.reduce_max(t_desc_belief)
                self.t_desc_belief = t_desc_belief_norm

            optimizer = tf.train.AdamOptimizer(config.translator.step_size)

            varz = self.v_model + self.v_desc

            self.t_loss = self.t_desc_loss + self.t_model_loss
            self.t_train_op = optimizer.minimize(
                    self.t_loss, var_list=varz)
