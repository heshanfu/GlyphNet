"""Generator and discriminator model definitions

These networks learn to communicate flat vectors between each other
via images.
"""

import code
import os

import tensorflow as tf


def swish(x):
    return tf.nn.sigmoid(x) * x


def make_name(block_name, layer_name, index=None):
    if index is None:
        return f'{block_name}_{layer_name}'
    else:
        return f'{block_name}_{layer_name}_{index}'


def conv_block(x, filters, block_name, index=None, pooling=False, one_by_one=False, sigmoid=False):
    """Typical convolution block with flag to control if downsampling or not
    """
    _make_name = lambda layer_name: make_name(block_name, layer_name, index)
    kernel = 1 if one_by_one else 3
    stride = 2 if pooling else 1
    activation = swish if not sigmoid else 'sigmoid'
    x = tf.keras.layers.Conv2D(filters, kernel, stride, padding='same', name=_make_name('conv'))(x)
    x = tf.keras.layers.BatchNormalization(name=_make_name('bn'))(x)
    x = tf.keras.layers.Activation(activation, name=_make_name('swish'))(x)
    return x


def deconv_block(x, filters, block_name, index):
    """Transposed convolution block which increases feature map scale 2x
    """
    _make_name = lambda layer_name: make_name(block_name, layer_name, index)
    x = tf.keras.layers.Conv2DTranspose(filters, (3, 3), (2, 2),
                                        padding='same',
                                        name=_make_name('deconv'))(x)
    x = tf.keras.layers.BatchNormalization(name=_make_name('bn'))(x)
    x = tf.keras.layers.Activation(swish, name=_make_name('swish'))(x)
    return x


def generator(vector_dim:int=32, R:int=4, last_channels:int=8, c:int=1):
    """Return a Keras generator model. This model takes an input vector
    and uses it to construct an image

    Args:
        vector_dim: the number of elements in the input vector
        R: the number of times to upsample feature maps (this determines image size)
        last_channels: the number of channels to use in last feature map (before prediction)
            This is used to calculate filter counts becuase the number of filters is divided
            by 2 after each transposed convolution
        c: number of output channels (1 for grayscale, 3 for color)
    """
    input_ = tf.keras.layers.Input(shape=(vector_dim,)) # 1-d feature map with VECTOR_DIM channels
    x = tf.keras.layers.Reshape((1, 1, vector_dim))(input_)
    filters = last_channels * (2 ** R)
    x = conv_block(x, filters, block_name='stem', one_by_one=True)
    filters /= 2
    for r in range(R):
        pre = deconv_block(x, int(filters), block_name='deconv_block', index=r + 1)
        x = conv_block(pre, int(filters), block_name='conv_1by1', index=r + 1, one_by_one=True)
        x = tf.keras.layers.Add(name=f'add_{r+1}')([pre, x])
        filters /= 2
    x = conv_block(x, c, block_name='prediction_conv', pooling=False, sigmoid=True)
    G = tf.keras.models.Model(inputs=[input_], outputs=[x])
    return G


def discriminator(vector_dim:int=32, R:int=4, first_channels:int=8, c:int=1):
    """Return a Keras discriminator model. This model takes an input image
    and uses it to form a prediction vector.

    Args:
        vector_dim: the number of elements of the prediction vector
        R: the number of times to downsample feature maps
        first_channels: the number of filters to use in the first convolutional layer.
            This is doubled after each sequential downpooling layer.
        c: the number of input channels (of the generated image)
    """
    input_dim = 2 ** R
    input_ = tf.keras.layers.Input(shape=(input_dim, input_dim, c))
    x = input_
    filters = first_channels * 2
    x = conv_block(x, filters, block_name='stem', pooling=False)
    for r in range(R):
        pre = conv_block(x, filters, block_name='conv_block', index=r + 1, pooling=True)
        x = conv_block(pre, int(filters), block_name='conv_1by1', index=r + 1, one_by_one=True)
        x = tf.keras.layers.Add(name=f'add_{r+1}')([pre, x])
        filters *= 2
    x = tf.keras.layers.GlobalAveragePooling2D(name='prediction_GAP')(x)
    x = tf.keras.layers.Dense(vector_dim + 1, name='prediction')(x)
    # prediction has no activation function, and the final element of the vector represents noise (no signal)
    D = tf.keras.models.Model(inputs=[input_], outputs=[x])
    return D


def make_generator_with_opt(opt):
    """Return a Keras generator according to argparse options
    """
    G = generator(opt.vector_dim, opt.r, opt.num_filters, opt.c)
    return G


def make_discriminator_with_opt(opt):
    """Return a Keras discriminator according to argparse options
    """
    D = discriminator(opt.vector_dim, opt.r, opt.num_filters, opt.c)
    return D


def adversarial_loss(encoding):
    """Return loss function for adversarial generator, dependent on signal encoding
    WIP -- NOT IMPLEMENTED
    """
    def one_hot_loss(y_true, y_pred):
        y_true = tf.nn.softmax(y_true)
        y_pred = tf.nn.softmax(y_pred)
        loss = tf.keras.losses.binary_crossentropy(y_true[:, -1], y_pred[:, -1])
        return loss

    def binary_loss(y_true, y_pred):
        """Only compare the last examples
        """
        loss = tf.keras.losses.binary_crossentropy(tf.nn.sigmoid(y_true[:, -1]), 
                                            1 - tf.nn.sigmoid(y_pred[:, -1]))
        return loss

    if encoding == 'one-hot':
        return one_hot_loss
    elif encoding == 'binary':
        return binary_loss
    else:
        raise RuntimeError(f"Encoding '{encoding}' not understood")


if __name__ == "__main__":
    VECTOR_DIM = 32
    R = 4
    num_filters = 8
    c = 1
    G = generator(VECTOR_DIM, R, num_filters, c)
    D = discriminator(VECTOR_DIM, R, num_filters, c)

    # generate visualizations
    os.makedirs('model_viz', exist_ok=True)
    tf.keras.utils.plot_model(G, to_file=os.path.join('model_viz', 'generator.png'), show_shapes=True)
    tf.keras.utils.plot_model(D, to_file=os.path.join('model_viz', 'discriminator.png'), show_shapes=True)
    G.summary()
    D.summary()
