for k in shipped:1 hidden:1 hidden:2 hidden:3 large:1; do
  kind=${k%%:*}; seed=${k##*:}
  python3 -B /p/render.py $seed $kind /w/$kind$seed/data && python3 -B /p/bf.py /w/$kind$seed/data /w/$kind$seed
done
echo ALL_DONE
