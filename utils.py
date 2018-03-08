import os,sys
import numpy as np
#import tensorflow as tf
import random
#import cv2,time
from skimage.util import random_noise
from skimage import transform
#from tensorflow.python.client import device_lib

#10 digit + blank + space

#num_train_samples = 128000

channel = 1
image_width=120
image_height=32
num_features=image_height*channel
SPACE_INDEX=0
SPACE_TOKEN=''
aug_rate=100
maxPrintLen = 18

tf.app.flags.DEFINE_boolean('Use_CRNN',True, 'use Densenet or CRNN')
tf.app.flags.DEFINE_boolean('restore',False, 'whether to restore from the latest checkpoint')
tf.app.flags.DEFINE_string('checkpoint_dir', './checkpoint/', 'the checkpoint dir')
tf.app.flags.DEFINE_float('initial_learning_rate', 1e-2, 'inital lr')
tf.app.flags.DEFINE_integer('num_layers', 2, 'number of layer')
tf.app.flags.DEFINE_integer('num_hidden', 256, 'number of hidden')
tf.app.flags.DEFINE_integer('num_epochs', 10000, 'maximum epochs')
tf.app.flags.DEFINE_integer('batch_size', 256, 'the batch_size')
tf.app.flags.DEFINE_integer('save_steps', 1000, 'the step to save checkpoint')
tf.app.flags.DEFINE_integer('validation_steps', 500, 'the step to validation')
tf.app.flags.DEFINE_float('decay_rate', 0.99, 'the lr decay rate')
tf.app.flags.DEFINE_integer('decay_steps', 1000, 'the lr decay_step for optimizer')
tf.app.flags.DEFINE_float('beta1', 0.9, 'parameter of adam optimizer beta1')
tf.app.flags.DEFINE_float('beta2', 0.999, 'adam parameter beta2')
tf.app.flags.DEFINE_float('momentum', 0.9, 'the momentum')
tf.app.flags.DEFINE_string('log_dir', './log', 'the logging dir')
FLAGS=tf.app.flags.FLAGS

#num_batches_per_epoch = int(num_train_samples/FLAGS.batch_size)

#charset = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ()&./\'-:!\\?><,|@[]'
charset='0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'
#charset='0123456789ABCDEFGHJKLMNPQRSTUVWXYZ'
num_classes=len(charset)+2

encode_maps={}
decode_maps={}
for i,char in enumerate(charset,1):
    encode_maps[char]=i
    decode_maps[i]=char
encode_maps[SPACE_TOKEN]=SPACE_INDEX
decode_maps[SPACE_INDEX]=SPACE_TOKEN

def preprocess(im,angle=5,lr_crop=0.05,ud_crop=0.02):
    angle=np.random.random_sample()*angle#0-30
    '''lr_crop=np.random.random_sample()*lr_crop
    ud_crop=np.random.random_sample()*ud_crop
    seed=np.random.randint(0,4)
    if seed==0:
        im=im[0:int(im.shape[0]*(1-ud_crop)),int(im.shape[1]*lr_crop):]
    if seed==1:
        im=im[0:int(im.shape[0]*(1-ud_crop)),0:int(im.shape[1]*(1-lr_crop))]
    if seed==2:
        im = im[int(im.shape[0]*ud_crop):, 0:int(im.shape[1] * (1 - lr_crop))]
    if seed==3:
        im = im[int(im.shape[0] * ud_crop):,int(im.shape[1]*lr_crop):]
   # im=np.fliplr(im)#左右翻转
    #im=np.flipud(im)#上下翻转'''
    #im=transform.rotate(im,angle)
    seed=1
    #seed=np.random.randint(0,2)
    if seed==1:
        im=random_noise(im,'gaussian')#add noise
    return  im*255

class DataIterator:
    def __init__(self, data_dir):
        self.image_names = []
        self.image = []
        self.labels=[]
        if(os.path.isdir(data_dir)):
            for root, sub_folder, file_list in os.walk(data_dir):
                for file_path in file_list:
                    image_name = os.path.join(root,file_path)
                    self.image_names.append(image_name)
                    im = cv2.imread(image_name,0)#/255.#read the gray image
                    img = cv2.resize(im, (image_width, image_height))
                    img = img.swapaxes(0, 1)
                    self.image.append(np.array(img[:,:,np.newaxis]))
                    #self.image.append(img/255)
                    code = image_name.split('_')[1]
                    code = [SPACE_INDEX if code == SPACE_TOKEN else encode_maps[c] for c in list(code)]
                    self.labels.append(code)
                    
        if(os.path.isfile(data_dir)):
            path=os.path.split(data_dir)[0]
            file = open(data_dir) 
            while 1:
                line = file.readline()
                if not line:
                    break
                #pass # do something
                f_name=line.split(" ")[0].rstrip()
                image_name=os.path.split(f_name)[1]
                self.image_names.append(image_name)
#                print(image_name)
                im = cv2.imread(path+'/'+f_name,0)/255.#read the gray image
                img = cv2.resize(im, (image_width, image_height))
                img = img.swapaxes(0, 1)
                self.image.append(np.array(img[:,:,np.newaxis]))
                #self.image.append(img/255)
                code = image_name.split('_')[1]
#                print(code)
                code = [SPACE_INDEX if code == SPACE_TOKEN else encode_maps[c] for c in list(code)]
                self.labels.append(code)
                
            file.close()
   

    @property
    def size(self):
        return len(self.labels)

    def the_label(self,indexs):
        labels=[]
        for i in indexs:
            labels.append(self.labels[i])
        return labels

    #@staticmethod
    #def data_augmentation(images):
    #    if FLAGS.random_flip_up_down:
    #        images = tf.image.random_flip_up_down(images)
    #    if FLAGS.random_brightness:
    #        images = tf.image.random_brightness(images, max_delta=0.3)
    #    if FLAGS.random_contrast:
    #        images = tf.image.random_contrast(images, 0.8, 1.2)
    #    return images

    def input_index_generate_batch(self,index=None):
        if index:
            image_batch=[self.image[i] for i in index]
            label_batch=[self.labels[i] for i in index]
        else:
            # get the whole data as input
            image_batch=self.image
            label_batch=self.labels

        def get_input_lens(sequences):
            lengths = np.asarray([len(s) for s in sequences], dtype=np.int64)
            return sequences,lengths
        batch_inputs,batch_seq_len = get_input_lens(np.array(image_batch))
        #batch_inputs,batch_seq_len = pad_input_sequences(np.array(image_batch))
        batch_labels = sparse_tuple_from_label(label_batch)
        return batch_inputs,batch_seq_len,batch_labels

def accuracy_calculation(original_seq,decoded_seq,ignore_value=-1,isPrint = True):
    if  len(original_seq)!=len(decoded_seq):
        print('original lengths is different from the decoded_seq,please check again')
        return 0
    count = 0
    for i,origin_label in enumerate(original_seq):
        decoded_label  = [j for j in decoded_seq[i] if j!=ignore_value]
        if isPrint and i<maxPrintLen:
            print('seq{0:4d}: origin: {1} decoded:{2}'.format(i,origin_label,decoded_label))
        if origin_label == decoded_label: count+=1
    return count*1.0/len(original_seq)

def sparse_tuple_from_label(sequences, dtype=np.int32):
    """Create a sparse representention of x.
    Args:
        sequences: a list of lists of type dtype where each element is a sequence
    Returns:
        A tuple with (indices, values, shape)
    """
    indices = []
    values = []

    for n, seq in enumerate(sequences):
        indices.extend(zip([n]*len(seq), range(0,len(seq),1)))
        values.extend(seq)

    indices = np.asarray(indices, dtype=np.int64)
    values = np.asarray(values, dtype=dtype)
    shape = np.asarray([len(sequences), np.asarray(indices).max(0)[1]+1], dtype=np.int64)

    return indices, values, shape

def pad_input_sequences(sequences, maxlen=None, dtype=np.float32,
                  padding='post', truncating='post', value=0.):
    '''Pads each sequence to the same length: the length of the longest
    sequence.
        If maxlen is provided, any sequence longer than maxlen is truncated to
        maxlen. Truncation happens off either the beginning or the end
        (default) of the sequence. Supports post-padding (default) and
        pre-padding.
        Args:
            sequences: list of lists where each element is a sequence
            maxlen: int, maximum length
            dtype: type to cast the resulting sequence.
            padding: 'pre' or 'post', pad either before or after each sequence.
            truncating: 'pre' or 'post', remove values from sequences larger
            than maxlen either in the beginning or in the end of the sequence
            value: float, value to pad the sequences to the desired value.
        Returns
            x: numpy array with dimensions (number_of_sequences, maxlen)
            lengths: numpy array with the original sequence lengths
    '''
    lengths = np.asarray([len(s) for s in sequences], dtype=np.int64)

    nb_samples = len(sequences)
    if maxlen is None:
        maxlen = np.max(lengths)

    # take the sample shape from the first non empty sequence
    # checking for consistency in the main loop below.
    sample_shape = tuple()
    for s in sequences:
        if len(s) > 0:
            sample_shape = np.asarray(s).shape[1:]
            break

    x = (np.ones((nb_samples, maxlen) + sample_shape) * value).astype(dtype)
    for idx, s in enumerate(sequences):
        if len(s) == 0:
            continue  # empty list was found
        if truncating == 'pre':
            trunc = s[-maxlen:]
        elif truncating == 'post':
            trunc = s[:maxlen]
        else:
            raise ValueError('Truncating type "%s" not understood' % truncating)

        # check `trunc` has expected shape
        trunc = np.asarray(trunc, dtype=dtype)
        if trunc.shape[1:] != sample_shape:
            raise ValueError('Shape of sample %s of sequence at position %s is different from expected shape %s' %
                             (trunc.shape[1:], idx, sample_shape))

        if padding == 'post':
            x[idx, :len(trunc)] = trunc
        elif padding == 'pre':
            x[idx, -len(trunc):] = trunc
        else:
            raise ValueError('Padding type "%s" not understood' % padding)
    return x, lengths
