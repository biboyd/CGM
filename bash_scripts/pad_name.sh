#!/bin/bash
outfile=$2
infile=$1
text='FOGGIE - B. Boyd (MSU) 2019 - https://foggie.science'
ffmpeg -i $infile -vf drawtext="fontsize=30:text='FOGGIE - B. Boyd (MSU) 2019 - https\://foggie.science':x=(w-text_w)/1.02:y=(h-text_h)/1.01" $outfile
echo $text


