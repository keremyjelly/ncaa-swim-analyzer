for f in ncaa*.txt; do
  new_name=$(echo "$f" | tr E e)
  mv "$f" "$new_name"
done

