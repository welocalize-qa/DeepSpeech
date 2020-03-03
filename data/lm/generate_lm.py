import argparse
import os
import subprocess
from collections import Counter
from urllib import request

import progressbar


# ======================================================================================================================

def convert_and_filter_topk(args):
    """ Convert to lowercase, count word occurrences and save top-k words to a file """

    counter = Counter()
    data_lower = os.path.join(args.output_dir, 'lower.txt')

    print('\nConverting to lowercase and counting word occurrences ...')
    with open(data_lower, 'w+', encoding='utf8') as file_out:
        with open(args.input_txt, encoding='utf8') as file_in:
            for line in progressbar.progressbar(file_in):
                line_lower = line.lower()
                counter.update(line_lower.split())
                file_out.write(line_lower)

    # Save top-k words
    print('\nSaving top {} words'.format(args.top_k))
    vocab_str = '\n'.join(word for word, count in counter.most_common(args.top_k))
    vocab_path = 'vocab-{}.txt'.format(args.top_k)
    vocab_path = os.path.join(args.output_dir, vocab_path)
    with open(vocab_path, 'w+') as file:
        file.write(vocab_str)

    return data_lower, vocab_str


# ======================================================================================================================

def build_lm(args, data_lower, vocab_str):
    print('\nCreating ARPA file ...')
    lm_path = os.path.join(args.output_dir, 'lm.arpa')
    subprocess.check_call([
        args.kenlm_bins + 'lmplz',
        '--order', str(args.arpa_order),
        '--temp_prefix', args.output_dir,
        '--memory', args.max_arpa_memory,
        '--text', data_lower,
        '--arpa', lm_path,
        '--prune', '0', '0', '1'
    ])

    # Filter LM using vocabulary of top 500k words
    print('\nFiltering ARPA file using vocabulary of top-k words ...')
    filtered_path = os.path.join(args.output_dir, 'lm_filtered.arpa')
    subprocess.run([
        args.kenlm_bins + 'filter',
        'single',
        'model:{}'.format(lm_path),
        filtered_path
    ], input=vocab_str.encode('utf-8'), check=True)

    # Quantize and produce trie binary.
    print('\nBuilding lm.binary ...')
    binary_path = os.path.join(args.output_dir, 'lm.binary')
    subprocess.check_call([
        args.kenlm_bins + 'build_binary',
        '-a', '255',
        '-q', '8',
        '-v',
        'trie',
        filtered_path,
        binary_path
    ])


# ======================================================================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Generate an lm.binary and top-k vocab for DeepSpeech.'
    )
    parser.add_argument(
        '--input_txt',
        help='File path to a .txt with sample sentences',
        type=str,
        required=True
    )
    parser.add_argument(
        '--output_dir',
        help='Directory path for the output',
        type=str,
        required=True
    )
    parser.add_argument(
        '--top_k',
        help='Use top_k most frequent words for the vocab.txt file',
        type=int,
        default=500000
    )
    parser.add_argument(
        '--download_librispeech',
        action='store_true'
    )
    parser.add_argument(
        '--kenlm_bins',
        help='File path to the kenlm binaries lmplz, filter and build_binary',
        type=str,
        default='/DeepSpeech/native_client/kenlm/build/bin/'
    )
    parser.add_argument(
        '--arpa_order',
        help='Order of k-grams in arpa-file generation',
        type=int,
        default=5
    )
    parser.add_argument(
        '--max_arpa_memory',
        help='Maximum allowed memory usage in arpa-file generation',
        type=str,
        default='75%'
    )
    args = parser.parse_args()

    if args.download_librispeech:
        # Grab corpus
        url = 'http://www.openslr.org/resources/11/librispeech-lm-norm.txt.gz'
        print('Downloading {} into {} ...'.format(url, args.input_txt + '.gz'))
        request.urlretrieve(url, args.input_txt + '.gz')
        print('Unzipping ... ')
        subprocess.check_call(['gunzip', args.input_txt + '.gz'])

    data_lower, vocab_str = convert_and_filter_topk(args)
    build_lm(args, data_lower, vocab_str)

    # Delete intermediate files
    os.remove(os.path.join(args.output_dir, 'lower.txt'))
    os.remove(os.path.join(args.output_dir, 'lm.arpa'))
    os.remove(os.path.join(args.output_dir, 'lm_filtered.arpa'))


# ======================================================================================================================

if __name__ == '__main__':
    main()
