import java.util.Collection;
import java.util.Iterator;

class Utility {
  public static String join(Collection<?> s, String delimiter) {
    StringBuilder builder = new StringBuilder();
    Iterator iter = s.iterator();
    while (iter.hasNext()) {
      builder.append(iter.next());
      if (!iter.hasNext()) {
        break;
      }
      builder.append(delimiter);
    }
    return builder.toString();
  }
}
