#pad the files
infile=$1
outfile=$2
og_width=1026
og_height=872

ffmpeg -i $infile -vf "pad=width=1106:height=942:x=80:y=30:color=white" $outfile  

